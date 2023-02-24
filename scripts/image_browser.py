import gradio as gr
import logging
import os
import random
import platform
import re
import shutil
import stat
import sys
import time
import modules.extras
import modules.ui
from modules import paths
from modules import script_callbacks
from modules import shared, scripts, images
from modules.shared import opts, cmd_opts
from modules.ui_common import plaintext_to_html
from modules.ui_components import ToolButton
from scripts.wib import wib_db
from PIL import Image
from PIL.ExifTags import TAGS
from PIL.JpegImagePlugin import JpegImageFile
from PIL.PngImagePlugin import PngImageFile
from pathlib import Path
from typing import List, Tuple
try:
    from send2trash import send2trash
    send2trash_installed = True
except ImportError:
    print("Image Browser: send2trash is not installed. recycle bin cannot be used.")
    send2trash_installed = False

yappi_do = False
favorite_tab_name = "Favorites"
default_tab_options = ["txt2img", "img2img", "txt2img-grids", "img2img-grids", "Extras", favorite_tab_name, "Others"]
tabs_list = opts.image_browser_active_tabs.split(", ") if hasattr(opts, "image_browser_active_tabs") else default_tab_options
num_of_imgs_per_page = 0
loads_files_num = 0
image_ext_list = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]
cur_ranking_value="0"
finfo_aes = {}
exif_cache = {}
finfo_exif = {}
aes_cache = {}
none_select = "Nothing selected"
refresh_symbol = '\U0001f504'  # 🔄
up_symbol = '\U000025b2'  # ▲
down_symbol = '\U000025bc'  # ▼
rebuild_symbol = '\U0001f50e\U0001f4c2'  # 🔎📂
current_depth = 0
init = True
copy_move = ["Move", "Copy"]
copied_moved = ["Moved", "Copied"]

path_maps = {
    "txt2img": opts.outdir_txt2img_samples,
    "img2img": opts.outdir_img2img_samples,
    "txt2img-grids": opts.outdir_txt2img_grids,
    "img2img-grids": opts.outdir_img2img_grids,
    "Extras": opts.outdir_extras_samples,
    favorite_tab_name: opts.outdir_save
}

# Logging
logger = logging.getLogger(__name__)
logger_mode = logging.ERROR
if hasattr(opts, "image_browser_logger_warning"):
    if opts.image_browser_logger_warning:
        logger_mode = logging.WARNING
if hasattr(opts, "image_browser_logger_debug"):
    if opts.image_browser_logger_debug:
        logger_mode = logging.DEBUG
logger.setLevel(logger_mode)
console_handler = logging.StreamHandler()
console_handler.setLevel(logger_mode)
logger.addHandler(console_handler)
# Debug logging
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"{sys.executable} {sys.version}")
    logger.debug(f"{platform.system()} {platform.version()}")
    try:
        git = os.environ.get('GIT', "git")
        commit_hash = os.popen(f"{git} rev-parse HEAD").read()
    except Exception as e:
        commit_hash = e
    logger.debug(f"{commit_hash}")
    logger.debug(f"Gradio {gr.__version__}")
    logger.debug(f"{paths.script_path}")
    with open(cmd_opts.ui_config_file, "r") as f:
        logger.debug(f.read())
    with open(cmd_opts.ui_settings_file, "r") as f:
        logger.debug(f.read())

def delete_recycle(filename):
    if opts.image_browser_delete_recycle and send2trash_installed:
        send2trash(filename)
    else:
        file = Path(filename)
        file.unlink()
    return

def img_path_subdirs_get(img_path):
    subdirs = []
    subdirs.append(none_select)
    for item in os.listdir(img_path):
        item_path = os.path.join(img_path, item)
        if os.path.isdir(item_path):
            subdirs.append(item_path)
    return gr.update(choices=subdirs)

def img_path_add_remove(img_dir, path_recorder, add_remove, img_path_depth):
    if add_remove == "add" or (add_remove == "remove" and img_dir in path_recorder):
        if add_remove == "add":
            path_recorder[img_dir] = {
                "depth": int(img_path_depth),
                "path_display": f"{img_dir} [{int(img_path_depth)}]"
            }
            wib_db.update_path_recorder(img_dir, path_recorder[img_dir]["depth"], path_recorder[img_dir]["path_display"])
        else:
            del path_recorder[img_dir]
            wib_db.delete_path_recorder(img_dir)
        path_recorder_formatted = [value.get("path_display") for key, value in path_recorder.items()]
        path_recorder_formatted = sorted(path_recorder_formatted, key=lambda x: natural_keys(x.lower()))

    if add_remove == "remove":
        selected = None
    else:
        selected = path_recorder[img_dir]["path_display"]
    return path_recorder, gr.update(choices=path_recorder_formatted, value=selected)

def sort_order_flip(turn_page_switch, sort_order):
    if sort_order == up_symbol:
        sort_order = down_symbol
    else:
        sort_order = up_symbol
    return 1, -turn_page_switch, sort_order

def read_path_recorder(path_recorder):
    path_recorder = wib_db.load_path_recorder()
    path_recorder_formatted = [value.get("path_display") for key, value in path_recorder.items()]
    path_recorder_formatted = sorted(path_recorder_formatted, key=lambda x: natural_keys(x.lower()))
    path_recorder_unformatted = list(path_recorder.keys())
    path_recorder_unformatted = sorted(path_recorder_unformatted, key=lambda x: natural_keys(x.lower()))

    return path_recorder, path_recorder_formatted, path_recorder_unformatted

def pure_path(path):
    if path == []:
        return path, 0
    match = re.search(r" \[(\d+)\]$", path)
    if match:
        path = path[:match.start()]
        depth = int(match.group(1))
    else:
        depth = 0
    return path, depth

def browser2path(img_path_browser):
    img_path, _ = pure_path(img_path_browser)
    return img_path

def totxt(file):
    base, _ = os.path.splitext(file)
    file_txt = base + '.txt'

    return file_txt

def tab_select(path_recorder):
    path_recorder, path_recorder_formatted, path_recorder_unformatted = read_path_recorder(path_recorder)
    return path_recorder, gr.update(choices=path_recorder_unformatted)

def reduplicative_file_move(src, dst):
    def same_name_file(basename, path):
        name, ext = os.path.splitext(basename)
        f_list = os.listdir(path)
        max_num = 0
        for f in f_list:
            if len(f) <= len(basename):
                continue
            f_ext = f[-len(ext):] if len(ext) > 0 else ""
            if f[:len(name)] == name and f_ext == ext:                
                if f[len(name)] == "(" and f[-len(ext)-1] == ")":
                    number = f[len(name)+1:-len(ext)-1]
                    if number.isdigit():
                        if int(number) > max_num:
                            max_num = int(number)
        return f"{name}({max_num + 1}){ext}"
    name = os.path.basename(src)
    save_name = os.path.join(dst, name)
    src_txt_exists = False
    if opts.image_browser_txt_files:
        src_txt = totxt(src)
        if os.path.exists(src_txt):
            src_txt_exists = True
    if not os.path.exists(save_name):
        if opts.image_browser_copy_image:
            shutil.copy2(src, dst)
            if opts.image_browser_txt_files and src_txt_exists:
                shutil.copy2(src_txt, dst)
        else:
            shutil.move(src, dst)
            if opts.image_browser_txt_files and src_txt_exists:
                shutil.move(src_txt, dst)
    else:
        name = same_name_file(name, dst)
        if opts.image_browser_copy_image:
            shutil.copy2(src, os.path.join(dst, name))
            if opts.image_browser_txt_files and src_txt_exists:
                shutil.copy2(src_txt, totxt(os.path.join(dst, name)))
        else:
            shutil.move(src, os.path.join(dst, name))
            if opts.image_browser_txt_files and src_txt_exists:
                shutil.move(src_txt, totxt(os.path.join(dst, name)))

def save_image(file_name, filenames, page_index, turn_page_switch, dest_path):
    if file_name is not None and os.path.exists(file_name):
        reduplicative_file_move(file_name, dest_path)
        message = f"<div style='color:#999'>{copied_moved[opts.image_browser_copy_image]} to {dest_path}</div>"
        if not opts.image_browser_copy_image:
            # Force page refresh with checking filenames
            filenames = []
            turn_page_switch = -turn_page_switch
    else:
        message = "<div style='color:#999'>Image not found (may have been already moved)</div>"

    return message, filenames, page_index, turn_page_switch

def delete_image(delete_num, name, filenames, image_index, visible_num):
    if name == "":
        return filenames, delete_num
    else:
        delete_num = int(delete_num)
        visible_num = int(visible_num)
        image_index = int(image_index)
        index = list(filenames).index(name)
        i = 0
        new_file_list = []
        for name in filenames:
            if i >= index and i < index + delete_num:
                if os.path.exists(name):
                    if visible_num == image_index:
                        new_file_list.append(name)
                        i += 1
                        continue
                    if opts.image_browser_delete_message:
                        print(f"Deleting file {name}")
                    delete_state = True
                    delete_recycle(name)
                    visible_num -= 1
                    if opts.image_browser_txt_files:
                        txt_file = totxt(name)
                        if os.path.exists(txt_file):
                            delete_recycle(txt_file)
                else:
                    print(f"File does not exist {name}")
            else:
                new_file_list.append(name)
            i += 1
    return new_file_list, 1, visible_num, delete_state

def traverse_all_files(curr_path, image_list, tabname_box, img_path_depth) -> List[Tuple[str, os.stat_result, str, int]]:
    global current_depth
    if curr_path == "":
        return image_list
    f_list = [(os.path.join(curr_path, entry.name), entry.stat()) for entry in os.scandir(curr_path)]
    for f_info in f_list:
        fname, fstat = f_info
        if os.path.splitext(fname)[1] in image_ext_list:
            image_list.append(f_info)
        elif stat.S_ISDIR(fstat.st_mode):
            if (opts.image_browser_with_subdirs and tabname_box != "Others") or (tabname_box == "Others" and img_path_depth != 0 and (current_depth < img_path_depth or img_path_depth < 0)):
                current_depth = current_depth + 1
                image_list = traverse_all_files(fname, image_list, tabname_box, img_path_depth)
                current_depth = current_depth - 1
    return image_list

def cache_exif(fileinfos):
    global finfo_exif, exif_cache, finfo_aes, aes_cache

    if yappi_do:
        import yappi
        import pandas as pd
        yappi.set_clock_type("wall")
        yappi.start()
    
    cache_exif_start = time.time()
    new_exif = 0
    new_aes = 0
    conn, cursor = wib_db.transaction_begin()
    for fi_info in fileinfos:
        if any(fi_info[0].endswith(ext) for ext in image_ext_list):
            found_exif = False
            found_aes = False
            if fi_info[0] in exif_cache:
                finfo_exif[fi_info[0]] = exif_cache[fi_info[0]]
                found_exif = True
            if fi_info[0] in aes_cache:
                finfo_aes[fi_info[0]] = aes_cache[fi_info[0]]
                found_aes = True
            if not found_exif or not found_aes:
                finfo_exif[fi_info[0]] = "0"
                exif_cache[fi_info[0]] = "0"
                finfo_aes[fi_info[0]] = "0"
                aes_cache[fi_info[0]] = "0"
                if fi_info[0].endswith(image_ext_list[3]) or fi_info[0].endswith(image_ext_list[4]) or fi_info[0].endswith(image_ext_list[5]):
                    allExif = False
                else:
                    if fi_info[0].endswith(image_ext_list[0]):
                        image = PngImageFile(fi_info[0])
                    else:
                        image = JpegImageFile(fi_info[0])
                    try:
                        allExif = modules.extras.run_pnginfo(image)[1]
                    except OSError as e:
                        if e.errno == 22:
                            logger.warning(f"Caught OSError with error code 22: {fi_info[0]}")
                        else:
                            raise
                if allExif:
                    finfo_exif[fi_info[0]] = allExif
                    exif_cache[fi_info[0]] = allExif
                    wib_db.update_exif_data(conn, fi_info[0], allExif)
                    new_exif = new_exif + 1
                    m = re.search("(?:aesthetic_score:|Score:) (\d+.\d+)", allExif)
                    if m:
                        aes_value = m.group(1)
                    else:
                        aes_value = "0"
                    finfo_aes[fi_info[0]] = aes_value
                    aes_cache[fi_info[0]] = aes_value
                    wib_db.update_aes_data(conn, fi_info[0], aes_value)
                    new_aes = new_aes + 1
                else:
                    try:
                        filename = os.path.splitext(fi_info[0])[0] + ".txt"
                        geninfo = ""
                        with open(filename) as f:
                            for line in f:
                                geninfo += line
                        finfo_exif[fi_info[0]] = geninfo
                        exif_cache[fi_info[0]] = geninfo
                        wib_db.update_exif_data(conn, fi_info[0], geninfo)
                        new_exif = new_exif + 1
                        m = re.search("(?:aesthetic_score:|Score:) (\d+.\d+)", geninfo)
                        if m:
                            aes_value = m.group(1)
                        else:
                            aes_value = "0"
                        finfo_aes[fi_info[0]] = aes_value
                        aes_cache[fi_info[0]] = aes_value
                        wib_db.update_aes_data(conn, fi_info[0], aes_value)
                        new_aes = new_aes + 1
                    except Exception:
                        logger.warning(f"No EXIF in image or txt file for {fi_info[0]}")
                        # Saved with defaults to not scan it again next time
                        finfo_exif[fi_info[0]] = "0"
                        exif_cache[fi_info[0]] = "0"
                        allExif = "0"
                        wib_db.update_exif_data(conn, fi_info[0], allExif)
                        new_exif = new_exif + 1
                        aes_value = "0"
                        finfo_aes[fi_info[0]] = aes_value
                        aes_cache[fi_info[0]] = aes_value
                        wib_db.update_aes_data(conn, fi_info[0], aes_value)
                        new_aes = new_aes + 1
    
    wib_db.transaction_end(conn, cursor)

    if yappi_do:
        yappi.stop()
        pd.set_option('display.float_format', lambda x: '%.6f' % x)
        yappi_stats = yappi.get_func_stats().strip_dirs()
        data = [(s.name, s.ncall, s.tsub, s.ttot, s.ttot/s.ncall) for s in yappi_stats]
        df = pd.DataFrame(data, columns=['name', 'ncall', 'tsub', 'ttot', 'tavg'])
        print(df.to_string(index=False))
        yappi.get_thread_stats().print_all()

    cache_exif_end = time.time()
    logger.debug(f"cache_exif: {new_exif}/{len(fileinfos)} cache_aes: {new_aes}/{len(fileinfos)} {round(cache_exif_end - cache_exif_start, 1)} seconds")

def exif_rebuild(exif_rebuild_button):
    global finfo_exif, exif_cache, finfo_aes, aes_cache
    if opts.image_browser_scan_exif:
        print("Rebuild start")
        exif_dirs = wib_db.get_exif_dirs()
        finfo_aes = {}
        exif_cache = {}
        finfo_exif = {}
        aes_cache = {}
        for key, value in exif_dirs.items():
            if os.path.exists(key):
                print(f"Rebuilding {key}")
                fileinfos = traverse_all_files(key, [], "", 0)
                cache_exif(fileinfos)
        print("Rebuild end")

    return exif_rebuild_button

def atof(text):
    try:
        retval = float(text)
    except ValueError:
        retval = text
    return retval

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    float regex comes from https://stackoverflow.com/a/12643073/190597
    '''
    return [ atof(c) for c in re.split(r'[+-]?([0-9]+(?:[.][0-9]*)?|[.][0-9]+)', text) ]


def get_all_images(dir_name, sort_by, sort_order, keyword, tabname_box, img_path_depth, ranking_filter, aes_filter, exif_keyword, negative_prompt_search):
    global current_depth
    current_depth = 0
    fileinfos = traverse_all_files(dir_name, [], tabname_box, img_path_depth)
    keyword = keyword.strip(" ")
    
    if opts.image_browser_scan_exif:
        cache_exif(fileinfos)
    
    if len(keyword) != 0:
        fileinfos = [x for x in fileinfos if keyword.lower() in x[0].lower()]
        filenames = [finfo[0] for finfo in fileinfos]
    if len(exif_keyword) != 0:
        if negative_prompt_search == "Yes":
            fileinfos = [x for x in fileinfos if exif_keyword.lower() in finfo_exif[x[0]].lower()]
        else:
            result = []
            for file_info in fileinfos:
                file_name = file_info[0]
                file_exif = finfo_exif[file_name].lower()
                start_index = file_exif.find("negative_prompt: ")
                end_index = file_exif.find("\n", start_index)
                if negative_prompt_search == "Only":
                    sub_string = file_exif[start_index:end_index].split("negative_prompt: ")[-1].strip()
                    if exif_keyword.lower() in sub_string:
                        result.append(file_info)
                else:
                    sub_string = file_exif[start_index:end_index].strip()
                    file_exif = file_exif.replace(sub_string, "")
                    
                    if exif_keyword.lower() in file_exif:
                        result.append(file_info)
            fileinfos = result
        filenames = [finfo[0] for finfo in fileinfos]
    if len(aes_filter) != 0:
        fileinfos = [x for x in fileinfos if finfo_aes[x[0]] >= aes_filter]
        filenames = [finfo[0] for finfo in fileinfos]   
    if ranking_filter != "All":
        fileinfos = [x for x in fileinfos if get_ranking(x[0]) in ranking_filter]
        filenames = [finfo[0] for finfo in fileinfos]
    if sort_by == "date":
        if sort_order == up_symbol:
            fileinfos = sorted(fileinfos, key=lambda x: x[1].st_mtime)
        else:
            fileinfos = sorted(fileinfos, key=lambda x: -x[1].st_mtime)
        filenames = [finfo[0] for finfo in fileinfos]
    elif sort_by == "path name":
        if sort_order == up_symbol:
            fileinfos = sorted(fileinfos)
        else:
            fileinfos = sorted(fileinfos, reverse=True)
        filenames = [finfo[0] for finfo in fileinfos]
    elif sort_by == "random":
        random.shuffle(fileinfos)
        filenames = [finfo[0] for finfo in fileinfos]
    elif sort_by == "ranking":
        finfo_ranked = {}
        for fi_info in fileinfos:
            finfo_ranked[fi_info[0]] = get_ranking(fi_info[0])
        if not down_symbol:
            fileinfos = dict(sorted(finfo_ranked.items(), key=lambda x: (x[1], x[0])))
        else:
            fileinfos = dict(reversed(sorted(finfo_ranked.items(), key=lambda x: (x[1], x[0]))))
        filenames = [finfo for finfo in fileinfos]
    elif sort_by == "aesthetic_score":
        fileinfo_aes = {}
        for finfo in fileinfos:
            fileinfo_aes[finfo[0]] = finfo_aes[finfo[0]]
        if down_symbol:
            fileinfos = dict(reversed(sorted(fileinfo_aes.items(), key=lambda x: (x[1], x[0]))))
        else:
            fileinfos = dict(sorted(fileinfo_aes.items(), key=lambda x: (x[1], x[0])))
        filenames = [finfo for finfo in fileinfos]
    else:
        sort_values = {}
        exif_info = dict(finfo_exif)
        if exif_info:
            for k, v in exif_info.items():
                match = re.search(r'(?<='+ sort_by.lower() + ":" ').*?(?=(,|$))', v.lower())
                if match:
                    sort_values[k] = match.group()
                else:
                    sort_values[k] = "0"
            if down_symbol:
                fileinfos = dict(reversed(sorted(fileinfos, key=lambda x: natural_keys(sort_values[x[0]]))))
            else:
                fileinfos = dict(sorted(fileinfos, key=lambda x: natural_keys(sort_values[x[0]])))
            filenames = [finfo for finfo in fileinfos]
        else:
            filenames = [finfo for finfo in fileinfos]
    return filenames

def get_image_page(img_path, page_index, filenames, keyword, sort_by, sort_order, tabname_box, img_path_depth, ranking_filter, aes_filter, exif_keyword, negative_prompt_search, delete_state):
    if img_path == "":
        return [], page_index, [],  "", "",  "", 0, "", delete_state

    img_path, _ = pure_path(img_path)
    if page_index == 1 or page_index == 0 or len(filenames) == 0:
        filenames = get_all_images(img_path, sort_by, sort_order, keyword, tabname_box, img_path_depth, ranking_filter, aes_filter, exif_keyword, negative_prompt_search)
    page_index = int(page_index)
    length = len(filenames)
    max_page_index = length // num_of_imgs_per_page + 1
    page_index = max_page_index if page_index == -1 else page_index
    page_index = 1 if page_index < 1 else page_index
    page_index = max_page_index if page_index > max_page_index else page_index
    idx_frm = (page_index - 1) * num_of_imgs_per_page
    image_list = filenames[idx_frm:idx_frm + num_of_imgs_per_page]
    
    visible_num = num_of_imgs_per_page if  idx_frm + num_of_imgs_per_page < length else length % num_of_imgs_per_page 
    visible_num = num_of_imgs_per_page if visible_num == 0 else visible_num

    load_info = "<div style='color:#999' align='center'>"
    load_info += f"{length} images in this directory, divided into {int((length + 1) // num_of_imgs_per_page  + 1)} pages"
    load_info += "</div>"
    
    delete_state = False
    return filenames, gr.update(value=page_index, label=f"Page Index ({page_index}/{max_page_index})"), image_list,  "", "",  "", visible_num, load_info, delete_state

def get_current_file(tabname_box, num, page_index, filenames):
    file = filenames[int(num) + int((page_index - 1) * num_of_imgs_per_page)]
    return file
    
def show_image_info(tabname_box, num, page_index, filenames, turn_page_switch):
    logger.debug(f"tabname_box, num, page_index, len(filenames), num_of_imgs_per_page: {tabname_box}, {num}, {page_index}, {len(filenames)}, {num_of_imgs_per_page}")
    if len(filenames) == 0:
        # This should only happen if webui was stopped and started again and the user clicks on one of the still displayed images.
        # The state with the filenames will be empty then. In that case we return None to prevent further errors and force a page refresh.
        turn_page_switch = -turn_page_switch
        file = None
        tm =  None
    else:
        file = filenames[int(num) + int((page_index - 1) * num_of_imgs_per_page)]
        tm =   "<div style='color:#999' align='right'>" + time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(os.path.getmtime(file))) + "</div>"
    return file, tm, num, file, turn_page_switch

def show_next_image_info(tabname_box, num, page_index, filenames, auto_next):
    file = filenames[int(num) + int((page_index - 1) * num_of_imgs_per_page)]
    tm =   "<div style='color:#999' align='right'>" + time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(os.path.getmtime(file))) + "</div>"
    if auto_next:
        num = int(num) + 1
    return file, tm, num, file, ""

def change_dir(img_dir, path_recorder, load_switch, img_path_browser, img_path_depth, img_path):
    warning = None
    img_path, _ = pure_path(img_path)
    img_path_depth_org = img_path_depth
    if img_dir == none_select:
        return warning, gr.update(visible=False), img_path_browser, path_recorder, load_switch, img_path, img_path_depth
    else:
        img_dir, img_path_depth = pure_path(img_dir)
        if warning is None:
            try:
                if os.path.exists(img_dir):
                    try:
                        f = os.listdir(img_dir)                
                    except:
                        warning = f"'{img_dir} is not a directory"
                else:
                    warning = "The directory does not exist"
            except:
                warning = "The format of the directory is incorrect"   
        if warning is None: 
            return "", gr.update(visible=True), img_path_browser, path_recorder, img_dir, img_dir, img_path_depth
        else:
            return warning, gr.update(visible=False), img_path_browser, path_recorder, load_switch, img_path, img_path_depth_org

def update_move_text_one(btn):
    btn_text = " ".join(btn.split()[1:])
    return f"{copy_move[opts.image_browser_copy_image]} {btn_text}"

def update_move_text(favorites_btn, to_dir_btn):
    return update_move_text_one(favorites_btn), update_move_text_one(to_dir_btn)

def get_ranking(filename):
    ranking_value = wib_db.select_ranking(filename)
    return ranking_value

def create_tab(tabname, current_gr_tab):
    global init, exif_cache, aes_cache
    dir_name = None
    others_dir = False
    path_recorder = {}
    path_recorder_formatted = []
    path_recorder_unformatted = []
    
    if init:
        wib_db.check()
        exif_cache = wib_db.load_exif_data(exif_cache)
        aes_cache = wib_db.load_aes_data(aes_cache)
        init = False
    
    path_recorder, path_recorder_formatted, path_recorder_unformatted = read_path_recorder(path_recorder)

    if tabname in path_maps:
        dir_name = path_maps[tabname]
    elif tabname == "Others":
        others_dir = True
    elif os.path.isdir(tabname):
        dir_name = tabname
    else:
        raise RuntimeError(f"Invalid tab name: {tabname}")

    if not others_dir:
        dir_name = str(Path(dir_name))
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

    with gr.Row():                 
        path_recorder = gr.State(path_recorder)
        with gr.Column(scale=10):
            warning_box = gr.HTML("<p>&nbsp")
        with gr.Column(scale=5, visible=(tabname==favorite_tab_name)):
            gr.HTML(f"<p>Favorites path from settings: {opts.outdir_save}")

    with gr.Row(visible=others_dir):
        with gr.Column(scale=10):
            img_path = gr.Textbox(dir_name, label="Images directory", placeholder="Input images directory", interactive=others_dir)
        with gr.Column(scale=1):
            img_path_depth = gr.Number(value="0", label="Sub directory depth")
        with gr.Column(scale=1):
            img_path_save_button = gr.Button(value="Add to / replace in saved directories")

    with gr.Row(visible=others_dir):
        with gr.Column(scale=10):
            img_path_browser = gr.Dropdown(choices=path_recorder_formatted, label="Saved directories")
        with gr.Column(scale=1):
            img_path_remove_button = gr.Button(value="Remove from saved directories")

    with gr.Row(visible=others_dir): 
        with gr.Column(scale=10):
            img_path_subdirs = gr.Dropdown(choices=[none_select], value=none_select, label="Sub directories", interactive=True, elem_id=f"{tabname}_img_path_subdirs")
        with gr.Column(scale=1):
            img_path_subdirs_button = gr.Button(value="Get sub directories")

    with gr.Row(visible=others_dir): 
        with gr.Column(scale=10):
            gr.Dropdown(visible=False)
        with gr.Column(scale=1):
            exif_rebuild_button = gr.Button(value=f"{rebuild_symbol} Rebuild exif cache")
        
    with gr.Row(visible=not others_dir, elem_id=f"{tabname}_image_browser") as main_panel:
        with gr.Column():  
            with gr.Row():    
                with gr.Column(scale=2):    
                    with gr.Row():       
                        first_page = gr.Button('First Page')
                        prev_page = gr.Button('Prev Page', elem_id=f"{tabname}_image_browser_prev_page")
                        page_index = gr.Number(value=1, label="Page Index")
                        refresh_index_button = ToolButton(value=refresh_symbol)
                        next_page = gr.Button('Next Page', elem_id=f"{tabname}_image_browser_next_page")
                        end_page = gr.Button('End Page') 
                    with gr.Row():
                        ranking = gr.Radio(value="None", choices=["1", "2", "3", "4", "5", "None"], label="ranking", elem_id=f"{tabname}_image_browser_ranking", interactive=True, visible=False)
                        auto_next = gr.Checkbox(label="Next Image After Ranking (To be implemented)", interactive=False, visible=False)
                    with gr.Row():
                        image_gallery = gr.Gallery(show_label=False, elem_id=f"{tabname}_image_browser_gallery").style(grid=opts.image_browser_page_columns)
                    with gr.Row() as delete_panel:
                        with gr.Column(scale=1):
                            delete_num = gr.Number(value=1, interactive=True, label="delete next")
                        with gr.Column(scale=3):
                            delete = gr.Button('Delete', elem_id=f"{tabname}_image_browser_del_img_btn")

                with gr.Column(scale=1): 
                    with gr.Row(scale=0.5):
                        sort_by = gr.Dropdown(value="date", choices=["path name", "date", "aesthetic_score", "random", "cfg scale", "steps", "seed", "sampler", "size", "model", "model hash", "ranking"], label="sort by")
                        sort_order = ToolButton(value=down_symbol)
                    with gr.Row():
                        keyword = gr.Textbox(value="", label="filename keyword")
                    with gr.Row():
                            exif_keyword = gr.Textbox(value="", label="exif keyword")
                            negative_prompt_search = gr.Radio(value="No", choices=["No", "Yes", "Only"], label="Search negative prompt", interactive=True)
                    with gr.Column():
                        ranking_filter = gr.Radio(value="All", choices=["All", "1", "2", "3", "4", "5", "None"], label="ranking filter", interactive=True)
                    with gr.Row():  
                        aes_filter = gr.Textbox(value="", label="minimum aesthetic_score")
                    with gr.Row():
                        with gr.Column():
                            img_file_info = gr.Textbox(label="Generate Info", interactive=False, lines=6)
                            img_file_name = gr.Textbox(value="", label="File Name", interactive=False)
                            img_file_time= gr.HTML()
                    with gr.Row(elem_id=f"{tabname}_image_browser_button_panel", visible=False) as button_panel:
                        if tabname != favorite_tab_name:
                            favorites_btn = gr.Button(f'{copy_move[opts.image_browser_copy_image]} to favorites', elem_id=f"{tabname}_image_browser_favorites_btn")
                        try:
                            send_to_buttons = modules.generation_parameters_copypaste.create_buttons(["txt2img", "img2img", "inpaint", "extras"])
                        except:
                            pass
                    with gr.Row(elem_id=f"{tabname}_image_browser_to_dir_panel", visible=False) as to_dir_panel:
                        with gr.Box():
                            with gr.Row():
                                to_dir_path = gr.Textbox(label="Directory path")
                            with gr.Row():
                                to_dir_saved = gr.Dropdown(choices=path_recorder_unformatted, label="Saved directories")
                            with gr.Row():
                                to_dir_btn = gr.Button(f'{copy_move[opts.image_browser_copy_image]} to directory', elem_id=f"{tabname}_image_browser_to_dir_btn")

                    with gr.Row():
                        collected_warning = gr.HTML()


                    # hidden items
                    with gr.Row(visible=False): 
                        renew_page = gr.Button("Renew Page", elem_id=f"{tabname}_image_browser_renew_page")
                        visible_img_num = gr.Number()                     
                        tabname_box = gr.Textbox(tabname)
                        image_index = gr.Textbox(value=-1)
                        set_index = gr.Button('set_index', elem_id=f"{tabname}_image_browser_set_index")
                        filenames = gr.State([])
                        all_images_list = gr.State()
                        hidden = gr.Image(type="pil")
                        info1 = gr.Textbox()
                        info2 = gr.Textbox()
                        load_switch = gr.Textbox(value="load_switch", label="load_switch")
                        to_dir_load_switch = gr.Textbox(value="to dir load_switch", label="to_dir_load_switch")
                        turn_page_switch = gr.Number(value=1, label="turn_page_switch")
                        img_path_add = gr.Textbox(value="add")
                        img_path_remove = gr.Textbox(value="remove")
                        delete_state = gr.Checkbox(value=False, elem_id=f"{tabname}_image_browser_delete_state")
                        favorites_path = gr.Textbox(value=opts.outdir_save)
                        mod_keys = ""
                        if opts.image_browser_mod_ctrl_shift:
                            mod_keys = f"{mod_keys}CS"
                        elif opts.image_browser_mod_shift:
                            mod_keys = f"{mod_keys}S"
                        image_browser_mod_keys = gr.Textbox(value=mod_keys, elem_id=f"{tabname}_image_browser_mod_keys")

    change_dir_outputs = [warning_box, main_panel, img_path_browser, path_recorder, load_switch, img_path, img_path_depth]
    img_path.submit(change_dir, inputs=[img_path, path_recorder, load_switch, img_path_browser, img_path_depth, img_path], outputs=change_dir_outputs)
    img_path_browser.change(change_dir, inputs=[img_path_browser, path_recorder, load_switch, img_path_browser, img_path_depth, img_path], outputs=change_dir_outputs)
    # img_path_browser.change(browser2path, inputs=[img_path_browser], outputs=[img_path])
    to_dir_saved.change(change_dir, inputs=[to_dir_saved, path_recorder, to_dir_load_switch, to_dir_saved, img_path_depth, to_dir_path], outputs=[warning_box, main_panel, to_dir_saved, path_recorder, to_dir_load_switch, to_dir_path, img_path_depth])

    #delete
    delete.click(delete_image, inputs=[delete_num, img_file_name, filenames, image_index, visible_img_num], outputs=[filenames, delete_num, visible_img_num, delete_state])
    delete.click(fn=None, _js="image_browser_delete", inputs=[delete_num, tabname_box, image_index], outputs=None) 
    if tabname == favorite_tab_name:
        img_file_name.change(fn=update_move_text_one, inputs=[to_dir_btn], outputs=[to_dir_btn])
    else:
        favorites_btn.click(save_image, inputs=[img_file_name, filenames, page_index, turn_page_switch, favorites_path], outputs=[collected_warning, filenames, page_index, turn_page_switch])
        img_file_name.change(fn=update_move_text, inputs=[favorites_btn, to_dir_btn], outputs=[favorites_btn, to_dir_btn])
    to_dir_btn.click(save_image, inputs=[img_file_name, filenames, page_index, turn_page_switch, to_dir_path], outputs=[collected_warning, filenames, page_index, turn_page_switch])

    #turn page
    first_page.click(lambda s:(1, -s) , inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])
    next_page.click(lambda p, s: (p + 1, -s), inputs=[page_index, turn_page_switch], outputs=[page_index, turn_page_switch])
    prev_page.click(lambda p, s: (p - 1, -s), inputs=[page_index, turn_page_switch], outputs=[page_index, turn_page_switch])
    end_page.click(lambda s: (-1, -s), inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])    
    load_switch.change(lambda s:(1, -s), inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])
    keyword.submit(lambda s:(1, -s), inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])
    exif_keyword.submit(lambda s:(1, -s), inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])
    aes_filter.submit(lambda s:(1, -s), inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])
    sort_by.change(lambda s:(1, -s), inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])
    ranking_filter.change(lambda s:(1, -s), inputs=[turn_page_switch], outputs=[page_index, turn_page_switch])
    page_index.submit(lambda s: -s, inputs=[turn_page_switch], outputs=[turn_page_switch])
    renew_page.click(lambda s: -s, inputs=[turn_page_switch], outputs=[turn_page_switch])
    refresh_index_button.click(lambda p, s:(p, -s), inputs=[page_index, turn_page_switch], outputs=[page_index, turn_page_switch])
    img_path_depth.change(lambda s: -s, inputs=[turn_page_switch], outputs=[turn_page_switch])

    turn_page_switch.change(
        fn=get_image_page, 
        inputs=[img_path, page_index, filenames, keyword, sort_by, sort_order, tabname_box, img_path_depth, ranking_filter, aes_filter, exif_keyword, negative_prompt_search, delete_state], 
        outputs=[filenames, page_index, image_gallery, img_file_name, img_file_time, img_file_info, visible_img_num, warning_box, delete_state]
    )
    turn_page_switch.change(fn=None, inputs=[tabname_box], outputs=None, _js="image_browser_turnpage")
    turn_page_switch.change(fn=lambda:(gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)), inputs=None, outputs=[delete_panel, button_panel, ranking, to_dir_panel])

    sort_order.click(
        fn=sort_order_flip,
        inputs=[turn_page_switch, sort_order],
        outputs=[page_index, turn_page_switch, sort_order]
    )

    # Others
    img_path_subdirs_button.click(
        fn=img_path_subdirs_get, 
        inputs=[img_path], 
        outputs=[img_path_subdirs]
    )
    img_path_subdirs.change(
        fn=change_dir, 
        inputs=[img_path_subdirs, path_recorder, load_switch, img_path_browser, img_path_depth, img_path], 
        outputs=change_dir_outputs
    )
    img_path_save_button.click(
        fn=img_path_add_remove, 
        inputs=[img_path, path_recorder, img_path_add, img_path_depth], 
        outputs=[path_recorder, img_path_browser]
    )
    img_path_remove_button.click(
        fn=img_path_add_remove, 
        inputs=[img_path, path_recorder, img_path_remove, img_path_depth],
        outputs=[path_recorder, img_path_browser]
    )
    exif_rebuild_button.click(
        fn=exif_rebuild, 
        inputs=[exif_rebuild_button],
        outputs=[exif_rebuild_button]
    )

    # other functions
    set_index.click(show_image_info, _js="image_browser_get_current_img", inputs=[tabname_box, image_index, page_index, filenames, turn_page_switch], outputs=[img_file_name, img_file_time, image_index, hidden, turn_page_switch])
    set_index.click(fn=lambda:(gr.update(visible=True), gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)), inputs=None, outputs=[delete_panel, button_panel, ranking, to_dir_panel])
    img_file_name.change(fn=lambda : "", inputs=None, outputs=[collected_warning])
    img_file_name.change(get_ranking, inputs=img_file_name, outputs=ranking)

   
    hidden.change(fn=run_pnginfo, inputs=[hidden, img_path, img_file_name], outputs=[info1, img_file_info, info2])
    
    #ranking
    ranking.change(wib_db.update_ranking, inputs=[img_file_name, ranking])
    #ranking.change(show_next_image_info, _js="image_browser_get_current_img", inputs=[tabname_box, image_index, page_index, auto_next], outputs=[img_file_name, img_file_time, image_index, hidden])
        
    try:
        modules.generation_parameters_copypaste.bind_buttons(send_to_buttons, hidden, img_file_info)
    except:
        pass
    
    if not others_dir:
        current_gr_tab.select(
            fn=tab_select, 
            inputs=[path_recorder],
            outputs=[path_recorder, to_dir_saved]
            )
    
def run_pnginfo(image, image_path, image_file_name):
    if image is None:
        return '', '', ''
    geninfo, items = images.read_info_from_image(image)
    items = {**{'parameters': geninfo}, **items}

    info = ''
    for key, text in items.items():
        info += f"""
<div>
<p><b>{plaintext_to_html(str(key))}</b></p>
<p>{plaintext_to_html(str(text))}</p>
</div>
""".strip()+"\n"
    
    if geninfo is None:
        try:
            filename = os.path.splitext(image_file_name)[0] + ".txt"
            geninfo = ""
            with open(filename) as f:
                for line in f:
                    geninfo += line
        except Exception:
            logger.warning(f"No EXIF in image or txt file")
    return '', geninfo, info


def on_ui_tabs():
    global num_of_imgs_per_page
    global loads_files_num
    num_of_imgs_per_page = int(opts.image_browser_page_columns * opts.image_browser_page_rows)
    loads_files_num = int(opts.image_browser_pages_perload * num_of_imgs_per_page)
    with gr.Blocks(analytics_enabled=False) as image_browser:
        with gr.Tabs(elem_id="image_browser_tabs_container") as tabs:
            for tab in tabs_list:
                tab_name = os.path.basename(tab) if os.path.isdir(tab) else tab
                with gr.Tab(tab_name, elem_id=f"{tab}_image_browser_container") as current_gr_tab:
                    with gr.Blocks(analytics_enabled=False) :
                        create_tab(tab, current_gr_tab)
        gr.Checkbox(opts.image_browser_preload, elem_id="image_browser_preload", visible=False)
        gr.Textbox(",".join(tabs_list), elem_id="image_browser_tabnames_list", visible=False)
    return (image_browser , "Image Browser", "image_browser"),

def move_setting(options, section, added):
    try:
        old_value = shared.opts.__getattr__(options[3])
    except AttributeError:
        old_value = None
    try:
        new_value = shared.opts.__getattr__(options[0])
    except AttributeError:
        new_value = None
    if old_value is not None and new_value is None:
        # Add new option
        shared.opts.add_option(options[0], shared.OptionInfo(options[1], options[2], section=section))
        shared.opts.__setattr__(options[0], old_value)
        added = added + 1
        # Remove old option
        shared.opts.data.pop(options[3], None)

    return added

def on_ui_settings():
    image_browser_options = []
    # [current setting_name], [default], [label], [old setting_name]
    active_tabs_description = f"List of active tabs. Available options are {', '.join(default_tab_options)}. Custom folders are also supported by specifying their path."
    image_browser_options.append(("image_browser_active_tabs", ", ".join(default_tab_options), active_tabs_description, None))
    image_browser_options.append(("image_browser_with_subdirs", True, "Include images in sub directories", "images_history_with_subdirs"))
    image_browser_options.append(("image_browser_preload", False, "Preload images at startup", "images_history_preload"))
    image_browser_options.append(("image_browser_copy_image", False, "Move buttons copy instead of move", "images_copy_image"))
    image_browser_options.append(("image_browser_delete_message", True, "Print image deletion messages to the console", "images_delete_message"))
    image_browser_options.append(("image_browser_txt_files", True, "Move/Copy/Delete matching .txt files", "images_txt_files"))
    image_browser_options.append(("image_browser_logger_warning", False, "Print warning logs to the console", "images_logger_warning"))
    image_browser_options.append(("image_browser_logger_debug", False, "Print debug logs to the console", "images_logger_debug"))
    image_browser_options.append(("image_browser_delete_recycle", False, "Use recycle bin when deleting images", "images_delete_recycle"))
    image_browser_options.append(("image_browser_scan_exif", True, "Scan Exif-/.txt-data (slower, but required for exif-keyword-search)", "images_scan_exif"))
    image_browser_options.append(("image_browser_mod_shift", False, "Change CTRL keybindings to SHIFT", None))
    image_browser_options.append(("image_browser_mod_ctrl_shift", False, "or to CTRL+SHIFT", None))

    image_browser_options.append(("image_browser_page_columns", 6, "Number of columns on the page", "images_history_page_columns"))
    image_browser_options.append(("image_browser_page_rows", 6, "Number of rows on the page", "images_history_page_rows"))
    image_browser_options.append(("image_browser_pages_perload", 20, "Minimum number of pages per load", "images_history_pages_perload"))

    section = ('image-browser', "Image Browser")
    # Move historic setting names to current names
    added = 0
    for i in range(len(image_browser_options)):
        if image_browser_options[i][3] is not None:
            added = move_setting(image_browser_options[i], section, added)
    if added > 0:
        shared.opts.save(shared.config_filename)

    for i in range(len(image_browser_options)):
        shared.opts.add_option(image_browser_options[i][0], shared.OptionInfo(image_browser_options[i][1], image_browser_options[i][2], section=section))

script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_ui_tabs(on_ui_tabs)
