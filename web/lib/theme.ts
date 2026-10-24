export const THEME_KEY = "theme";

/** Inlined in <head> so a saved theme applies before first paint and never flashes the other one. */
export const THEME_BOOT_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
