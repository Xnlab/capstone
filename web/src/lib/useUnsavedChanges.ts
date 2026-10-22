"use client";

import { useEffect, useRef } from "react";

export function useUnsavedChanges(dirty: boolean) {
  const pending = useRef(dirty);
  useEffect(() => { pending.current = dirty; }, [dirty]);
  useEffect(() => {
    let approvedUntil = 0;
    const confirmLeave = () => !pending.current || window.confirm("저장하지 않은 변경사항이 있습니다. 저장하지 않고 나갈까요?");
    const unload = (event: BeforeUnloadEvent) => {
      if (pending.current && Date.now() > approvedUntil) { event.preventDefault(); event.returnValue = ""; }
    };
    const click = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return;
      const target = new URL(anchor.href, location.href);
      if (target.origin === location.origin && target.pathname === location.pathname && target.search === location.search) return;
      if (!confirmLeave()) { event.preventDefault(); event.stopPropagation(); }
      else approvedUntil = Date.now() + 1000;
    };
    // Navigation API supports cancelling browser back/forward in current Chromium.
    const navigation = (window as Window & { navigation?: EventTarget }).navigation;
    const traverse = (event: Event) => {
      if ((event as Event & { navigationType?: string }).navigationType === "traverse" && event.cancelable && !confirmLeave()) event.preventDefault();
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", click, true);
    navigation?.addEventListener("navigate", traverse);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true); navigation?.removeEventListener("navigate", traverse); };
  }, []);
  return () => { pending.current = false; };
}
