import { useEffect, useRef, useState } from "react";
import { Camera, CameraOff, ScanBarcode } from "lucide-react";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

export default function BarcodeScanner({ open, onClose, onDetected }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const detectorRef = useRef(null);
  const [error, setError] = useState("");
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    let timer;
    let video;
    const start = async () => {
      setError("");
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Tu navegador no permite acceder a la cámara.");
        return;
      }
      if (!("BarcodeDetector" in window)) {
        setError("Este navegador no soporta lectura automática de códigos. Puedes escribir el código manualmente.");
        return;
      }
      try {
        const formats = await window.BarcodeDetector.getSupportedFormats();
        const wanted = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "itf", "codabar"];
        detectorRef.current = new window.BarcodeDetector({ format: wanted.filter((x) => formats.includes(x)) });
        streamRef.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
        video = videoRef.current;
        if (!video) return;
        video.srcObject = streamRef.current;
        await video.play();
        setScanning(true);
        const loop = async () => {
          if (!video || !detectorRef.current) return;
          try {
            const codes = await detectorRef.current.detect(video);
            const value = codes?.[0]?.rawValue;
            if (value) { onDetected(value); return; }
          } catch (_) {}
          timer = requestAnimationFrame(loop);
        };
        timer = requestAnimationFrame(loop);
      } catch (e) {
        setScanning(false);
        setError(e?.name === "NotAllowedError" ? "Permite el acceso a la cámara para escanear." : "No pudimos iniciar la cámara.");
      }
    };
    start();
    return () => {
      if (timer) cancelAnimationFrame(timer);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      if (video) video.srcObject = null;
      detectorRef.current = null;
      setScanning(false);
    };
  }, [open, onDetected]);

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-lg">
      <DialogHeader><DialogTitle className="font-heading flex items-center gap-2"><ScanBarcode className="w-5 h-5 text-primary"/>Escanear código de barras</DialogTitle></DialogHeader>
      <div className="space-y-3">
        <div className="relative aspect-video overflow-hidden rounded-2xl bg-slate-950 border">
          <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
          {scanning && <div className="absolute inset-x-10 top-1/2 border-t-2 border-primary shadow-lg" />}
          {!scanning && <div className="absolute inset-0 flex items-center justify-center text-center p-6 text-white"><CameraOff className="w-8 h-8 mx-auto mb-2"/><p className="text-sm">{error || "Preparando cámara…"}</p></div>}
        </div>
        <p className="text-xs text-muted-foreground">Coloca el código dentro del área de lectura. El producto se seleccionará automáticamente.</p>
        {error && <Button type="button" variant="outline" className="w-full" onClick={() => window.location.reload()}><Camera className="w-4 h-4 mr-2"/>Intentar nuevamente</Button>}
      </div>
    </DialogContent>
  </Dialog>;
}
