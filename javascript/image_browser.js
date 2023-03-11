const image_browser_click_image = function() {
    if (!this.classList?.contains("transform")) {
        const gallery = image_browser_get_parent_by_class(this, "image_browser_container");
        const gallery_items = Array.from(gallery.querySelectorAll(".gallery-item"));
        // List of gallery item indices that are currently hidden in the image browser.
        const hidden_indices_list = gallery_items.filter(elem => elem.style.display === 'none').map(elem => gallery_items.indexOf(elem));
        if (hidden_indices_list.length > 0) {
            setTimeout(image_browser_hide_gallery_items, 10, hidden_indices_list, gallery);
        }
    }
    image_browser_set_image_info(this);
}

function image_browser_get_parent_by_class(item, class_name) {
    let parent = item.parentElement;
    while(!parent.classList.contains(class_name)){
        parent = parent.parentElement;
    }
    return parent;  
}

function image_browser_get_parent_by_tagname(item, tagname) {
    let parent = item.parentElement;
    tagname = tagname.toUpperCase()
    while(parent.tagName != tagname){
        parent = parent.parentElement;
    }  
    return parent;
}

function image_browser_hide_gallery_items(hidden_indices_list, gallery) {
    const gallery_items = gallery.querySelectorAll(".gallery-item");
    // The number of gallery items that are currently hidden in the image browser.
    const num = Array.from(gallery_items).filter(elem => elem.style.display === 'none').length;
    if (num == hidden_indices_list.length) {
        setTimeout(image_browser_hide_gallery_items, 10, hidden_indices_list, gallery);
    }
    hidden_indices_list.forEach(i => gallery_items[i].style.display = 'none');
}

function image_browser_set_image_info(gallery_item) {
    const gallery_items = image_browser_get_parent_by_tagname(gallery_item, "DIV").querySelectorAll(".gallery-item");
    // Finds the index of the specified gallery item within the visible gallery items in the image browser.
    const index = Array.from(gallery_items).filter(elem => elem.style.display !== 'none').indexOf(gallery_item);
    const gallery = image_browser_get_parent_by_class(gallery_item, "image_browser_container");
    const set_btn = gallery.querySelector(".image_browser_set_index");
    const curr_idx = set_btn.getAttribute("img_index", index);
    if (curr_idx != index) {
        set_btn.setAttribute("img_index", index);
    }
    set_btn.click();
}

function image_browser_get_current_img(tab_base_tag, img_index, page_index, filenames, turn_page_switch) {
    return [
        tab_base_tag,
        gradioApp().getElementById(tab_base_tag + '_image_browser_set_index').getAttribute("img_index"),
        page_index,
		filenames,
		turn_page_switch
    ];
}

function image_browser_delete(del_num, tab_base_tag, image_index) {
    image_index = parseInt(image_index);
    const tab = gradioApp().getElementById(tab_base_tag + '_image_browser');
    const set_btn = tab.querySelector(".image_browser_set_index");
    const gallery_items = Array.from(tab.querySelectorAll('.gallery-item')).filter(item => item.style.display !== 'none');
    const img_num = gallery_items.length / 2;
    del_num = Math.min(img_num - image_index, del_num)
    if (img_num <= del_num) {
        // If all images are deleted, we reload the browser page.
        setTimeout(function(tab_base_tag) {
            gradioApp().getElementById(tab_base_tag + '_image_browser_renew_page').click();
        }, 30, tab_base_tag);
    } else {
        // After deletion of the image, we have to navigate to the next image (or wraparound).
        for (let i = 0; i < del_num; i++) {
            gallery_items[image_index + i].style.display = 'none';
            gallery_items[image_index + i + img_num].style.display = 'none';
        }
        const next_img = gallery_items.find((elem, i) => elem.style.display !== 'none' && i > image_index);
        const btn = next_img || gallery_items[image_index - 1];
        setTimeout(function(btn){btn.click()}, 30, btn);
    }

}

function image_browser_turnpage(tab_base_tag) {
    const gallery_items = gradioApp().getElementById(tab_base_tag + '_image_browser').querySelectorAll(".gallery-item");
    gallery_items.forEach(function(elem) {
        elem.style.display = 'block';
    });
}

function image_browser_gototab(tabname, tabsId = "tabs") {
	Array.from(
		gradioApp().querySelectorAll(`#${tabsId} > div:first-child button`)
	).forEach((button) => {
		if (button.textContent.trim() === tabname) {
			button.click();
		}
	});
}

async function image_browser_get_image_for_ext(tab_base_tag, image_index) {
    var image_browser_image = gradioApp().querySelectorAll(`#${tab_base_tag}_image_browser_gallery .gallery-item`)[image_index];

	const canvas = document.createElement("canvas");
	const image = document.createElement("img");
	image.src = image_browser_image.querySelector("img").src;

	await image.decode();

	canvas.width = image.width;
	canvas.height = image.height;

	canvas.getContext("2d").drawImage(image, 0, 0);

	return canvas.toDataURL();
}

function image_browser_openoutpaint_send(tab_base_tag, image_index, image_browser_prompt, image_browser_neg_prompt, name = "WebUI Resource") {
    image_browser_get_image_for_ext(tab_base_tag, image_index)
		.then((dataURL) => {
			// Send to openOutpaint
			openoutpaint_send_image(dataURL, name);

			// Send prompt to openOutpaint
			const tab = get_uiCurrentTabContent().id;

			const prompt = image_browser_prompt;
            const negPrompt = image_browser_neg_prompt;
            openoutpaint.frame.contentWindow.postMessage({
                key: openoutpaint.key,
                type: "openoutpaint/set-prompt",
                prompt,
                negPrompt,
            });

			// Change Tab
            image_browser_gototab("openOutpaint");
		})
}

async function image_browser_controlnet_send(toTab,tab_base_tag, image_index, controlnetNum) {
    const dataURL = await image_browser_get_image_for_ext(tab_base_tag, image_index);
    const blob = await (await fetch(dataURL)).blob();
    const dt = new DataTransfer();
    dt.items.add(new File([blob], "ImageBrowser.png", { type: blob.type }));
    const container = gradioApp().querySelector(
        toTab === "txt2img" ? "#txt2img_script_container" : "#img2img_script_container"
    );
    const accordion = container.querySelector("#controlnet .transition");
    if (accordion.classList.contains("rotate-90")) accordion.click();

    const tab = container.querySelectorAll(
        "#controlnet > div:nth-child(2) > .tabs > .tabitem, #controlnet > div:nth-child(2) > div:not(.tabs)"
    )[controlnetNum];
    if (tab.classList.contains("tabitem"))
        tab.parentElement.firstElementChild.querySelector(`:nth-child(${Number(controlnetNum) + 1})`).click();

    const input = tab.querySelector("input[type='file']");
    try {
        input.previousElementSibling.previousElementSibling.querySelector("button[aria-label='Clear']").click();
    } catch (e) {}

    input.value = "";
    input.files = dt.files;
    input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));

    image_browser_gototab(toTab);
};

function image_browser_controlnet_send_txt2img(tab_base_tag, image_index, controlnetNum) {
    image_browser_controlnet_send("txt2img", tab_base_tag, image_index, controlnetNum);
}
  
function image_browser_controlnet_send_img2img(tab_base_tag, image_index, controlnetNum) {
    image_browser_controlnet_send("img2img", tab_base_tag, image_index, controlnetNum);
}

function image_browser_init() {
    const tab_base_tags = gradioApp().getElementById("image_browser_tab_base_tags_list");
    if (tab_base_tags) {
        image_browser_tab_base_tags_list = tab_base_tags.querySelector("textarea").value.split(",");
        image_browser_tab_base_tags_list.forEach(function(tab_base_tag) {
            gradioApp().getElementById(tab_base_tag + '_image_browser').classList.add("image_browser_container");
            gradioApp().getElementById(tab_base_tag + '_image_browser_set_index').classList.add("image_browser_set_index");
            gradioApp().getElementById(tab_base_tag + '_image_browser_del_img_btn').classList.add("image_browser_del_img_btn");
            gradioApp().getElementById(tab_base_tag + '_image_browser_gallery').classList.add("image_browser_gallery");
        });

        //preload
        const tab_btns = gradioApp().getElementById("image_browser_tabs_container").querySelector("div").querySelectorAll("button");
        tab_btns.forEach(function(btn, i) {
            const tab_base_tag = image_browser_tab_base_tags_list[i];
            btn.setAttribute("tab_base_tag", tab_base_tag);
            btn.addEventListener('click', function() {
                const tabs_box = gradioApp().getElementById("image_browser_tabs_container");
                if (!tabs_box.classList.contains(this.getAttribute("tab_base_tag"))) {
                    gradioApp().getElementById(this.getAttribute("tab_base_tag") + "_image_browser_renew_page").click();
                    tabs_box.classList.add(this.getAttribute("tab_base_tag"));
                }
            });
        });
        if (gradioApp().getElementById("image_browser_preload").querySelector("input").checked) {
             setTimeout(function(){tab_btns[0].click()}, 100);
        }

    } else {
        setTimeout(image_browser_init, 500);
    }
}

let timer;
let image_browser_tab_base_tags_list = "";
setTimeout(image_browser_init, 500);
document.addEventListener("DOMContentLoaded", function() {
    const mutationObserver = new MutationObserver(function(m) {
        if (image_browser_tab_base_tags_list != "") {
            image_browser_tab_base_tags_list.forEach(function(tab_base_tag) {
                const tab_gallery_items = gradioApp().querySelectorAll('#' + tab_base_tag + '_image_browser .gallery-item');
                tab_gallery_items.forEach(function(gallery_item) {
                    gallery_item.addEventListener('click', image_browser_click_image, true);
                    document.onkeyup = function(e) {
                        if (!image_browser_active()) {
                            return;
                        }
                        clearTimeout(timer)
                        timer = setTimeout(() => {
                            let gallery_btn = gradioApp().getElementById(image_browser_current_tab() + "_image_browser_gallery").getElementsByClassName('gallery-item !flex-none !h-9 !w-9 transition-all duration-75 !ring-2 !ring-orange-500 hover:!ring-orange-500 svelte-1g9btlg');
                            gallery_btn = gallery_btn && gallery_btn.length > 0 ? gallery_btn[0] : null;
                            if (gallery_btn) {
                                image_browser_click_image.call(gallery_btn)
                            }
                        }, 500);
                    }
                });

                const cls_btn = gradioApp().getElementById(tab_base_tag + '_image_browser_gallery').querySelector("svg");
                if (cls_btn) {
                    cls_btn.addEventListener('click', function() {
                        gradioApp().getElementById(tab_base_tag + '_image_browser_renew_page').click();
                    }, false);
                }
            });
        }
    });
    mutationObserver.observe(gradioApp(), { childList:true, subtree:true });
});

function image_browser_current_tab() {
    const tabs = gradioApp().getElementById("image_browser_tabs_container").querySelectorAll('[id$="_image_browser_container"]');

    for (const element of tabs) {
      if (element.style.display === "block") {
        const id = element.id;
        const index = id.indexOf("_image_browser_container");
        const tab_base_tag = id.substring(0, index);
        return tab_base_tag;
      }
    }
}

function image_browser_active() {
    const ext_active = gradioApp().getElementById("tab_image_browser");
    return ext_active && ext_active.style.display !== "none";
}

gradioApp().addEventListener("keydown", function(event) {
    // If we are not on the Image Browser Extension, dont listen for keypresses
    if (!image_browser_active()) {
        return;
    }

    // If the user is typing in an input field, dont listen for keypresses
    let target;
    if (!event.composed) { // We shouldn't get here as the Shadow DOM is always active, but just in case
        target = event.target;
    } else {
        target = event.composedPath()[0];
    }
    if (!target || target.nodeName === "INPUT" || target.nodeName === "TEXTAREA") {
      return;
    }

    const tab_base_tag = image_browser_current_tab();

    // Listens for keypresses 0-5 and updates the corresponding ranking (0 is the last option, None)
    if (event.code >= "Digit0" && event.code <= "Digit5") {
        const selectedValue = event.code.charAt(event.code.length - 1);
        const radioInputs = gradioApp().getElementById(tab_base_tag + "_image_browser_ranking").getElementsByTagName("input");
        for (const input of radioInputs) {
            if (input.value === selectedValue || (selectedValue === '0' && input === radioInputs[radioInputs.length - 1])) {
                input.checked = true;
                input.dispatchEvent(new Event("change"));
                break;
            }
        }
    }

    const mod_keys = gradioApp().querySelector(`#${tab_base_tag}_image_browser_mod_keys textarea`).value;
    let modifiers_pressed = false;
    if (mod_keys.indexOf("C") !== -1 && mod_keys.indexOf("S") !== -1) {
        if (event.ctrlKey && event.shiftKey) {
            modifiers_pressed = true;
        }
    } else if (mod_keys.indexOf("S") !== -1) {
        if (!event.ctrlKey && event.shiftKey) {
            modifiers_pressed = true;
        }
    } else {
        if (event.ctrlKey && !event.shiftKey) {
            modifiers_pressed = true;
        }
    }

    let modifiers_none = false;
    if (!event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey) {
        modifiers_none = true;
    }

    if (event.code == "KeyF" && modifiers_none) {
        if (tab_base_tag == "Favorites") {
            return;
        }
        const favoriteBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_favorites_btn");
        favoriteBtn.dispatchEvent(new Event("click"));
    }

    if (event.code == "KeyR" && modifiers_none) {
        const refreshBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_renew_page");
        refreshBtn.dispatchEvent(new Event("click"));
    }

    if (event.code == "Delete" && modifiers_none) {
        const deleteBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_del_img_btn");
        deleteBtn.dispatchEvent(new Event("click"));
    }

    // prevent left arrow following delete, instead refresh page
    if (event.code == "ArrowLeft" && modifiers_none) {
        const deleteState = gradioApp().getElementById(tab_base_tag + "_image_browser_delete_state").getElementsByClassName('gr-check-radio gr-checkbox')[0];
        if (deleteState.checked) {
            const refreshBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_renew_page");
            refreshBtn.dispatchEvent(new Event("click"));
        }
    }

    if (event.code == "ArrowLeft" && modifiers_pressed) {
        const prevBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_prev_page");
        prevBtn.dispatchEvent(new Event("click"));
    }

    if (event.code == "ArrowRight" && modifiers_pressed) {
        const nextBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_next_page");
        nextBtn.dispatchEvent(new Event("click"));
    }
});
