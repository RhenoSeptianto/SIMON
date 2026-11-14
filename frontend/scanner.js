// === SIMONADO LOCAL CAMERA SCANNER & QR WRITER ===
let activeScanStream = null;
let activeScanReader = null;

function stopCameraScanner() {
 try { activeScanReader?.reset?.(); } catch {}
 activeScanReader = null;
 if (activeScanStream) {
  activeScanStream.getTracks().forEach(t => { try { t.stop(); } catch {} });
  activeScanStream = null;
 }
 const dlg = document.querySelector('#scanDialog');
 if (dlg?.open) dlg.close();
}

async function openCameraScanner({ onScan, fallbackFocusSelector = '', title = 'Scan QR / Barcode Serial Number' } = {}) {
 if (!navigator.mediaDevices?.getUserMedia) {
  if (fallbackFocusSelector) {
   const el = document.querySelector(fallbackFocusSelector);
   if (el) { el.focus(); el.select?.(); }
  }
  toast('Kamera tidak tersedia. Silakan scan langsung dengan scanner USB atau ketik SN.', 'error');
  return;
 }
 let dlg = document.querySelector('#scanDialog');
 if (!dlg) {
  dlg = document.createElement('dialog');
  dlg.id = 'scanDialog';
  document.body.append(dlg);
 }
 dlg.style.maxWidth = '500px';
 dlg.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px">
  <h3 style="margin:0">${esc(title)}</h3>
  <button type="button" id="closeScanDialogBtn" class="secondary compact">Tutup</button>
 </div>
 <p class="muted" style="margin:0 0 10px;font-size:12px">Arahkan kamera belakang ke <b>QR Code</b> atau <b>Barcode</b> perangkat.</p>
 <div class="scan-video-wrap"><video id="scanVideoEl" playsinline muted autoplay></video><div class="scan-frame"></div></div>
 <p id="scanStatusMsg" class="muted" style="margin:10px 0 0;font-size:12px;text-align:center">Membuka kamera belakang...</p>`;
 dlg.showModal();
 dlg.oncancel = () => stopCameraScanner();
 document.querySelector('#closeScanDialogBtn').onclick = () => stopCameraScanner();

 try {
  const stream = await navigator.mediaDevices.getUserMedia({
   video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
   audio: false,
  });
  activeScanStream = stream;
  const video = document.querySelector('#scanVideoEl');
  video.srcObject = stream;
  await video.play();
  const statusEl = document.querySelector('#scanStatusMsg');
  if (statusEl) statusEl.textContent = 'Kamera aktif — arahkan ke barcode / QR Code...';

  if (window.ZXing?.BrowserMultiFormatReader) {
   const reader = new window.ZXing.BrowserMultiFormatReader();
   activeScanReader = reader;
   reader.decodeFromVideoElementContinuously(video, (result) => {
    if (!result) return;
    const text = String(result.getText ? result.getText() : result.text || '').trim();
    if (!text) return;
    stopCameraScanner();
    toast(`Berhasil scan: ${text}`);
    if (typeof onScan === 'function') onScan(text);
   });
  } else if ('BarcodeDetector' in window) {
   const detector = new window.BarcodeDetector({ formats: ['qr_code', 'code_128', 'code_39', 'ean_13', 'ean_8', 'data_matrix'] });
   const tick = async () => {
    if (!activeScanStream || !dlg.open) return;
    try {
     const codes = await detector.detect(video);
     if (codes?.length && codes[0].rawValue) {
      const text = String(codes[0].rawValue).trim();
      stopCameraScanner();
      toast(`Berhasil scan: ${text}`);
      if (typeof onScan === 'function') onScan(text);
      return;
     }
    } catch {}
    requestAnimationFrame(tick);
   };
   requestAnimationFrame(tick);
  } else {
   if (statusEl) statusEl.textContent = 'Browser tidak mendukung pembacaan barcode otomatis.';
  }
 } catch (err) {
  stopCameraScanner();
  if (fallbackFocusSelector) {
   const el = document.querySelector(fallbackFocusSelector);
   if (el) { el.focus(); el.select?.(); }
  }
  toast('Tidak dapat mengakses kamera (' + (err.message || 'ditolak') + '). Fokus diarahkan ke kolom SN.', 'error');
 }
}

function renderQrSvg(text, size = 180) {
 try {
  if (window.ZXing?.BrowserQRCodeSvgWriter) {
   const writer = new window.ZXing.BrowserQRCodeSvgWriter();
   const svgEl = writer.write(String(text || ''), size, size);
   svgEl.setAttribute('style', `width:${size}px;height:${size}px;background:#fff;padding:8px;border-radius:10px;border:1px solid var(--line)`);
   return svgEl.outerHTML;
  }
 } catch {}
 return '';
}
