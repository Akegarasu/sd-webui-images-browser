let image_browser_state = "free"
let image_browser_oldGradio
let image_browser_galleryItemName

onUiLoaded(image_browser_start)

function image_browser_delay(ms){return new Promise(resolve => setTimeout(resolve, ms))}

async function image_browser_lock(reason) {
    // Wait until lock removed
    let i = 0
    while (image_browser_state != "free") {
        await image_browser_delay(200)
        i = i + 1
        if (i === 150) {
            throw new Error("Still locked after 30 seconds. Please Reload UI.")
        }
    }
    // Lock
    image_browser_state = reason
}

async function image_browser_unlock() {
    image_browser_state = "free"
}

function isVersionSmaller(version1, version2) {
    let v1 = version1.split('.').map(Number)
    let v2 = version2.split('.').map(Number)
    for (let i = 0; i < Math.max(v1.length, v2.length); i++) {
        if ((v1[i] || 0) < (v2[i] || 0)) return true
        if ((v1[i] || 0) > (v2[i] || 0)) return false
    }
    return false
}

const image_browser_click_image = async function() {
    await image_browser_lock("image_browser_click_image")
    const gallery_items = image_browser_get_parent_by_tagname(this, "DIV").querySelectorAll(image_browser_image_browser_galleryItemNameDot)
    const index = Array.from(gallery_items).indexOf(this)
    const gallery = image_browser_get_parent_by_class(this, "image_browser_container")
    const set_btn = gallery.querySelector(".image_browser_set_index")
    const curr_idx = set_btn.getAttribute("img_index")
    if (curr_idx != index) {
        set_btn.setAttribute("img_index", index)
    }
    set_btn.click()
    await image_browser_unlock()
}

function image_browser_get_parent_by_class(item, class_name) {
    let parent = item.parentElement
    while(!parent.classList.contains(class_name)){
        parent = parent.parentElement
    }
    return parent
}

function image_browser_get_parent_by_tagname(item, tagname) {
    let parent = item.parentElement
    tagname = tagname.toUpperCase()
    while(parent.tagName != tagname){
        parent = parent.parentElement
    }  
    return parent
}

function image_browser_run_after_preview_load(tab_base_tag, func) {
    ob = new MutationObserver(async (mutationList, observer) => {
        elem = mutationList[0].target
        if (elem.classList.contains("hide")) { 
            func()
            observer.disconnect()
        }
    })
    ob.observe(
        gradioApp().querySelectorAll(`#${tab_base_tag}_image_browser_gallery .svelte-gjihhp`)[0],
        { attributes: true }
    )
}

async function image_browser_get_current_img(tab_base_tag, img_index, page_index, filenames, turn_page_switch, image_gallery) {
    await image_browser_lock("image_browser_get_current_img")
    img_index = gradioApp().getElementById(tab_base_tag + '_image_browser_set_index').getAttribute("img_index")
    image_browser_hide_loading_animation(true)
    gradioApp().dispatchEvent(new Event("image_browser_get_current_img"))
    image_browser_run_after_preview_load(tab_base_tag,() => image_browser_hide_loading_animation(false))
    await image_browser_unlock()
    return [
        tab_base_tag,
        img_index,
        page_index,
		filenames,
        turn_page_switch,
        image_gallery
    ]
}

function image_browser_hide_loading_animation(hidden) {
    if (hidden === true) {
        gradioApp().querySelectorAll("div[id^='image_browser_tab'][id$='image_browser_gallery']:not(.hide_loading)").forEach((elem) => {
            elem.classList.add("hide_loading")
        })
    } else { 
        gradioApp().querySelectorAll("div[id^='image_browser_tab'][id$='image_browser_gallery'].hide_loading").forEach((elem) => {
            elem.classList.remove("hide_loading")
        })
    }
}

async function image_browser_refresh_current_page_preview(wait_time = 200) { 
    await image_browser_delay(wait_time)
    const preview_div = gradioApp().querySelector('.preview')
    if (preview_div === null) return
    const tab_base_tag = image_browser_current_tab()
    const gallery = gradioApp().querySelector(`#${tab_base_tag}_image_browser`)
    const set_btn = gallery.querySelector(".image_browser_set_index")
    const curr_idx = parseInt(set_btn.getAttribute("img_index"))
    // no loading animation, so click immediately
    const gallery_items = gallery.querySelectorAll(image_browser_image_browser_galleryItemNameDot)
    const curr_image = gallery_items[curr_idx]
    curr_image.click()
}

async function image_browser_refresh_preview(wait_time = 200) { 
    await image_browser_delay(wait_time)
    const preview_div = gradioApp().querySelector('.preview')
    if (preview_div === null) return
    const tab_base_tag = image_browser_current_tab()
    const gallery = gradioApp().querySelector(`#${tab_base_tag}_image_browser`)
    const set_btn = gallery.querySelector(".image_browser_set_index")
    const curr_idx = set_btn.getAttribute("img_index")
    // wait for page loading...
    image_browser_run_after_preview_load(tab_base_tag, () => { 
        const gallery_items = gallery.querySelectorAll(image_browser_image_browser_galleryItemNameDot)
        const curr_image = gallery_items[curr_idx]
        curr_image.click()
    })
}

const image_browser_get_current_img_handler = (del_img_btn) => {
    // Prevent delete button spam
    del_img_btn.style.pointerEvents = "auto"
    del_img_btn.style.cursor = "default"
    del_img_btn.style.opacity = "1"
}

async function image_browser_select_image(tab_base_tag, img_index) {
    await image_browser_lock("image_browser_select_image")
    const del_img_btn = gradioApp().getElementById(tab_base_tag + "_image_browser_del_img_btn")
    // Prevent delete button spam
    del_img_btn.style.pointerEvents = "none"
    del_img_btn.style.cursor = "not-allowed"
    del_img_btn.style.opacity = "0.65"        

    const gallery = gradioApp().getElementById(tab_base_tag + "_image_browser_gallery")
    const gallery_items = gallery.querySelectorAll(image_browser_image_browser_galleryItemNameDot)
    if (img_index >= gallery_items.length || gallery_items.length == 0) {
        const refreshBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_renew_page")
        refreshBtn.dispatchEvent(new Event("click"))
    } else {
        const curr_image = gallery_items[img_index]
        curr_image.click()
    }
    await image_browser_unlock()

    // Prevent delete button spam
    gradioApp().removeEventListener("image_browser_get_current_img", () => image_browser_get_current_img_handler(del_img_btn))
    gradioApp().addEventListener("image_browser_get_current_img", () => image_browser_get_current_img_handler(del_img_btn))
}

async function image_browser_turnpage(tab_base_tag) {
    await image_browser_lock("image_browser_turnpage")
    const gallery_items = gradioApp().getElementById(tab_base_tag + '_image_browser').querySelectorAll(image_browser_image_browser_galleryItemNameDot)
    gallery_items.forEach(function(elem) {
        elem.style.display = 'block'
    })
    await image_browser_unlock()
}

function image_browser_gototab(tabname, tabsId = "tabs") {
	Array.from(
		gradioApp().querySelectorAll(`#${tabsId} > div:first-child button`)
	).forEach((button) => {
		if (button.textContent.trim() === tabname) {
			button.click()
		}
	})
}

async function image_browser_get_image_for_ext(tab_base_tag, image_index) {
    const image_browser_image = gradioApp().querySelectorAll(`#${tab_base_tag}_image_browser_gallery ${image_browser_image_browser_galleryItemNameDot}`)[image_index]

	const canvas = document.createElement("canvas")
	const image = document.createElement("img")
	image.src = image_browser_image.querySelector("img").src

	await image.decode()

	canvas.width = image.width
	canvas.height = image.height

	canvas.getContext("2d").drawImage(image, 0, 0)

	return canvas.toDataURL()
}

function image_browser_openoutpaint_send(tab_base_tag, image_index, image_browser_prompt, image_browser_neg_prompt, name = "WebUI Resource") {
    image_browser_get_image_for_ext(tab_base_tag, image_index)
		.then((dataURL) => {
			// Send to openOutpaint
			openoutpaint_send_image(dataURL, name)

			// Send prompt to openOutpaint
			const tab = get_uiCurrentTabContent().id

			const prompt = image_browser_prompt
            const negPrompt = image_browser_neg_prompt
            openoutpaint.frame.contentWindow.postMessage({
                key: openoutpaint.key,
                type: "openoutpaint/set-prompt",
                prompt,
                negPrompt,
            })

			// Change Tab
            image_browser_gototab("openOutpaint")
		})
}

async function image_browser_controlnet_send(toTab, tab_base_tag, image_index, controlnetNum) {
    const dataURL = await image_browser_get_image_for_ext(tab_base_tag, image_index)
    const blob = await (await fetch(dataURL)).blob()
    const dt = new DataTransfer()
    dt.items.add(new File([blob], "ImageBrowser.png", { type: blob.type }))
    const container = gradioApp().querySelector(
        toTab === "txt2img" ? "#txt2img_script_container" : "#img2img_script_container"
    )
    const accordion = container.querySelector("#controlnet .transition")
    if (accordion.classList.contains("rotate-90")) accordion.click()

    const tab = container.querySelectorAll(
        "#controlnet > div:nth-child(2) > .tabs > .tabitem, #controlnet > div:nth-child(2) > div:not(.tabs)"
    )[controlnetNum]
    if (tab.classList.contains("tabitem"))
        tab.parentElement.firstElementChild.querySelector(`:nth-child(${Number(controlnetNum) + 1})`).click()

    const input = tab.querySelector("input[type='file']")
    try {
        input.previousElementSibling.previousElementSibling.querySelector("button[aria-label='Clear']").click()
    } catch (e) {}

    input.value = ""
    input.files = dt.files
    input.dispatchEvent(new Event("change", { bubbles: true, composed: true }))

    image_browser_gototab(toTab)
}

function image_browser_controlnet_send_txt2img(tab_base_tag, image_index, controlnetNum) {
    image_browser_controlnet_send("txt2img", tab_base_tag, image_index, controlnetNum)
}
  
function image_browser_controlnet_send_img2img(tab_base_tag, image_index, controlnetNum) {
    image_browser_controlnet_send("img2img", tab_base_tag, image_index, controlnetNum)
}

function image_browser_class_add(tab_base_tag) {
    gradioApp().getElementById(tab_base_tag + '_image_browser').classList.add("image_browser_container")
    gradioApp().getElementById(tab_base_tag + '_image_browser_set_index').classList.add("image_browser_set_index")
    gradioApp().getElementById(tab_base_tag + '_image_browser_del_img_btn').classList.add("image_browser_del_img_btn")
    gradioApp().getElementById(tab_base_tag + '_image_browser_gallery').classList.add("image_browser_gallery")
}

function btnClickHandler(tab_base_tag, btn) {
    const tabs_box = gradioApp().getElementById("image_browser_tabs_container")
    if (!tabs_box.classList.contains(tab_base_tag)) {
        gradioApp().getElementById(tab_base_tag + "_image_browser_renew_page").click()
        tabs_box.classList.add(tab_base_tag)
    }
}

function image_browser_init() {
    const GradioVersion = gradioApp().getElementById("image_browser_gradio_version").querySelector("textarea").value
    if (isVersionSmaller(GradioVersion, "3.17")) {
        image_browser_oldGradio = true
        image_browser_galleryItemName = "gallery-item"
    } else {
        image_browser_oldGradio = false
        image_browser_galleryItemName = "thumbnail-item"
    }    
    image_browser_image_browser_galleryItemNameDot = "." + image_browser_galleryItemName
    
    const tab_base_tags = gradioApp().getElementById("image_browser_tab_base_tags_list")
    if (tab_base_tags) {
        const image_browser_tab_base_tags_list = tab_base_tags.querySelector("textarea").value.split(",")
        image_browser_tab_base_tags_list.forEach(function(tab_base_tag) {
            image_browser_class_add(tab_base_tag)
        })
        
        const tab_btns = gradioApp().getElementById("image_browser_tabs_container").querySelector("div").querySelectorAll("button")
        tab_btns.forEach(function(btn, i) {
            const tab_base_tag = image_browser_tab_base_tags_list[i]
            btn.setAttribute("tab_base_tag", tab_base_tag)
            btn.removeEventListener('click', () => btnClickHandler(tab_base_tag, btn))
            btn.addEventListener('click', () => btnClickHandler(tab_base_tag, btn))
        })
        
        //preload
        if (gradioApp().getElementById("image_browser_preload").querySelector("input").checked) {
             setTimeout(function(){tab_btns[0].click()}, 100)
        }
    }
    image_browser_keydown()
}

async function image_browser_wait_for_gallery_btn(tab_base_tag){ 
    await image_browser_delay(100)
    while (!gradioApp().getElementById(image_browser_current_tab() + "_image_browser_gallery").getElementsByClassName(image_browser_galleryItemName)) {
        await image_browser_delay(200)
    }
}

function image_browser_renew_page(tab_base_tag) {
    gradioApp().getElementById(tab_base_tag + '_image_browser_renew_page').click()
}

function image_browser_start() {
    image_browser_init()
    const mutationObserver = new MutationObserver(function(mutationsList) {
        const tab_base_tags = gradioApp().getElementById("image_browser_tab_base_tags_list")
        if (tab_base_tags) {
            const image_browser_tab_base_tags_list = tab_base_tags.querySelector("textarea").value.split(",")
            image_browser_tab_base_tags_list.forEach(function(tab_base_tag) {
                image_browser_class_add(tab_base_tag)
                const tab_gallery_items = gradioApp().querySelectorAll('#' + tab_base_tag + '_image_browser ' + image_browser_image_browser_galleryItemNameDot)
                tab_gallery_items.forEach(function(gallery_item) {
                    gallery_item.removeEventListener('click', image_browser_click_image, true)
                    gallery_item.addEventListener('click', image_browser_click_image, true)
                    document.onkeyup = async function(e) {
                        if (!image_browser_active()) {
                            return
                        }
                        const current_tab = image_browser_current_tab()
                        image_browser_wait_for_gallery_btn(current_tab).then(() => {
                            let gallery_btn
                            if (image_browser_oldGradio) {
                                gallery_btn = gradioApp().getElementById(current_tab + "_image_browser_gallery").getElementsByClassName(image_browser_galleryItemName + ' !flex-none !h-9 !w-9 transition-all duration-75 !ring-2 !ring-orange-500 hover:!ring-orange-500 svelte-1g9btlg')
                            } else {
                                gallery_btn = gradioApp().getElementById(current_tab + "_image_browser_gallery").querySelector(image_browser_image_browser_galleryItemNameDot + ' .selected')
                            }
                            gallery_btn = gallery_btn && gallery_btn.length > 0 ? gallery_btn[0] : null
                            if (gallery_btn) {
                                image_browser_click_image.call(gallery_btn)
                            }
                        })
                    }
                })

                const cls_btn = gradioApp().getElementById(tab_base_tag + '_image_browser_gallery').querySelector("svg")
                if (cls_btn) {
                    cls_btn.removeEventListener('click', () => image_browser_renew_page(tab_base_tag), false)
                    cls_btn.addEventListener('click', () => image_browser_renew_page(tab_base_tag), false)
                }
            })
        }
    })
    mutationObserver.observe(gradioApp(), { childList:true, subtree:true })
}

function image_browser_current_tab() {
    const tabs = gradioApp().getElementById("image_browser_tabs_container").querySelectorAll('[id$="_image_browser_container"]')
    const tab_base_tags = gradioApp().getElementById("image_browser_tab_base_tags_list")
    const image_browser_tab_base_tags_list = tab_base_tags.querySelector("textarea").value.split(",").sort((a, b) => b.length - a.length)
    for (const element of tabs) {
      if (element.style.display === "block") {
        const id = element.id
        const tab_base_tag = image_browser_tab_base_tags_list.find(element => id.startsWith(element)) || null
        return tab_base_tag
      }
    }
}

function image_browser_active() {
    const ext_active = gradioApp().getElementById("tab_image_browser")
    return ext_active && ext_active.style.display !== "none"
}

function image_browser_keydown() {
    gradioApp().addEventListener("keydown", function(event) {
        // If we are not on the Image Browser Extension, dont listen for keypresses
        if (!image_browser_active()) {
            return
        }

        // If the user is typing in an input field, dont listen for keypresses
        let target
        if (!event.composed) { // We shouldn't get here as the Shadow DOM is always active, but just in case
            target = event.target
        } else {
            target = event.composedPath()[0]
        }
        if (!target || target.nodeName === "INPUT" || target.nodeName === "TEXTAREA") {
        return
        }

        const tab_base_tag = image_browser_current_tab()

        // Listens for keypresses 0-5 and updates the corresponding ranking (0 is the last option, None)
        if (event.code >= "Digit0" && event.code <= "Digit5") {
            const selectedValue = event.code.charAt(event.code.length - 1)
            const radioInputs = gradioApp().getElementById(tab_base_tag + "_image_browser_ranking").getElementsByTagName("input")
            for (const input of radioInputs) {
                if (input.value === selectedValue || (selectedValue === '0' && input === radioInputs[radioInputs.length - 1])) {
                    input.checked = true
                    input.dispatchEvent(new Event("change"))
                    break
                }
            }
        }

        const mod_keys = gradioApp().querySelector(`#${tab_base_tag}_image_browser_mod_keys textarea`).value
        let modifiers_pressed = false
        if (mod_keys.indexOf("C") !== -1 && mod_keys.indexOf("S") !== -1) {
            if (event.ctrlKey && event.shiftKey) {
                modifiers_pressed = true
            }
        } else if (mod_keys.indexOf("S") !== -1) {
            if (!event.ctrlKey && event.shiftKey) {
                modifiers_pressed = true
            }
        } else {
            if (event.ctrlKey && !event.shiftKey) {
                modifiers_pressed = true
            }
        }

        let modifiers_none = false
        if (!event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey) {
            modifiers_none = true
        }

        if (event.code == "KeyF" && modifiers_none) {
            if (tab_base_tag == "image_browser_tab_favorites") {
                return
            }
            const favoriteBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_favorites_btn")
            favoriteBtn.dispatchEvent(new Event("click"))
        }

        if (event.code == "KeyR" && modifiers_none) {
            const refreshBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_renew_page")
            refreshBtn.dispatchEvent(new Event("click"))
        }

        if (event.code == "Delete" && modifiers_none) {
            const deleteBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_del_img_btn")
            deleteBtn.dispatchEvent(new Event("click"))
        }

        if (event.code == "ArrowLeft" && modifiers_pressed) {
            const prevBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_prev_page")
            prevBtn.dispatchEvent(new Event("click"))
        }

        if (event.code == "ArrowLeft" && modifiers_none) {
            const tab_base_tag = image_browser_current_tab()
            const set_btn = gradioApp().querySelector(`#${tab_base_tag}_image_browser .image_browser_set_index`)
            const curr_idx = parseInt(set_btn.getAttribute("img_index"))
            set_btn.setAttribute("img_index", curr_idx - 1)
            image_browser_refresh_current_page_preview()
        }
        
        if (event.code == "ArrowRight" && modifiers_pressed) {
            const nextBtn = gradioApp().getElementById(tab_base_tag + "_image_browser_next_page")
            nextBtn.dispatchEvent(new Event("click"))
        }

        if (event.code == "ArrowRight" && modifiers_none) {
            const tab_base_tag = image_browser_current_tab()
            const set_btn = gradioApp().querySelector(`#${tab_base_tag}_image_browser .image_browser_set_index`)
            const curr_idx = parseInt(set_btn.getAttribute("img_index"))
            set_btn.setAttribute("img_index", curr_idx + 1)
            image_browser_refresh_current_page_preview()
        }
    })
}
