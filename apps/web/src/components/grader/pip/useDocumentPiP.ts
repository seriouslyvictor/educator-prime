import { useCallback, useEffect, useRef, useState } from "react";

// Minimal ambient declaration for the Document Picture-in-Picture API
// (no built-in DOM types in TypeScript as of TS 5.7)
declare global {
  interface Window {
    documentPictureInPicture?: {
      requestWindow(options: { width: number; height: number }): Promise<Window>;
    };
  }
}

const APP_FONT =
  'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

function copyStylesIntoPiP(pipDoc: Document): void {
  const openerHead = document.head;
  const nodes = openerHead.querySelectorAll<HTMLElement>(
    'link[rel="stylesheet"], style',
  );
  for (const node of nodes) {
    pipDoc.head.appendChild(node.cloneNode(true));
  }
}

export interface UseDocumentPiPResult {
  isSupported: boolean;
  isOpen: boolean;
  pipWindow: Window | null;
  open(): Promise<void>;
  close(): void;
}

export function useDocumentPiP(): UseDocumentPiPResult {
  const isSupported = typeof window !== "undefined" && "documentPictureInPicture" in window;

  const [pipWindow, setPipWindow] = useState<Window | null>(null);
  const pipWindowRef = useRef<Window | null>(null);

  const close = useCallback(() => {
    if (pipWindowRef.current && !pipWindowRef.current.closed) {
      pipWindowRef.current.close();
    }
    pipWindowRef.current = null;
    setPipWindow(null);
  }, []);

  const open = useCallback(async () => {
    if (!window.documentPictureInPicture) return;

    // requestWindow must be called from a user gesture (click handler)
    const win = await window.documentPictureInPicture.requestWindow({
      width: 600,
      height: 680,
    });

    // Copy all stylesheets from the opener document
    copyStylesIntoPiP(win.document);

    // Set base body styles
    win.document.body.style.margin = "0";
    win.document.body.style.background = "var(--paper)";
    win.document.body.style.fontFamily = APP_FONT;

    // Listen for user closing the PiP window via Chrome's X button
    win.addEventListener("pagehide", () => {
      pipWindowRef.current = null;
      setPipWindow(null);
    });

    pipWindowRef.current = win;
    setPipWindow(win);
  }, []);

  // Clean up if component unmounts while PiP is open
  useEffect(() => {
    return () => {
      if (pipWindowRef.current && !pipWindowRef.current.closed) {
        pipWindowRef.current.close();
      }
    };
  }, []);

  return {
    isSupported,
    isOpen: pipWindow !== null,
    pipWindow,
    open,
    close,
  };
}
