# -*- coding: utf-8 -*-
"""Vision Agent Studio HTML page."""

AGENT_STUDIO_HTML = r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <title>NITEOS AI-студия</title>
  <style>
    :root{--bg:#070b10;--card:#0f151c;--line:#2b333d;--text:#eef2f6;--muted:#9aa6b2;--accent:#f5b942;--accent2:#5a8fd4}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Segoe UI,Arial,sans-serif;padding-bottom:78px}
    a{color:#9ec5ff;text-decoration:none}
    header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line);background:#0a1016;position:relative;z-index:5;flex-wrap:wrap}
    h1{margin:0;font-size:20px}
    .muted{color:var(--muted)}
    .btn{border:0;border-radius:10px;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer;background:#d8e0ea;color:#0a1016;text-decoration:none;display:inline-flex;align-items:center;justify-content:center}
    .btn.secondary{background:#1a222c;color:var(--text);border:1px solid var(--line)}
    .btn.accent{background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000}
    .btn:disabled{opacity:.45;cursor:not-allowed}
    .header-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;position:relative;z-index:6;justify-content:flex-end}
    .sales-hint{max-width:min(380px,56vw);font-size:12px;line-height:1.4;color:var(--muted);text-align:right}
    .sales-hint a{color:var(--accent);font-weight:700;text-decoration:none;white-space:nowrap}
    .sales-hint a:hover{text-decoration:underline}
    .layout{display:grid;grid-template-columns:minmax(220px,.9fr) minmax(340px,1.45fr) minmax(300px,1.05fr);gap:14px;padding:14px;min-height:calc(100vh - 64px)}
    @media(max-width:1100px){.layout{grid-template-columns:1fr}}
    .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;display:flex;flex-direction:column;gap:10px;min-height:0}
    .card.work-col{border-color:var(--line)}
    .card.chat-col{border-color:var(--line)}
    .col-kicker{display:block;width:fit-content;max-width:100%;margin:0;padding:0;border:0;background:none;box-shadow:none;font-size:11px;font-weight:700;letter-spacing:.02em;color:var(--muted);line-height:1.3}
    .col-kicker.work{color:#9ec5ff}
    .col-kicker.chat-label{color:var(--accent)}
    .card h2{margin:0;font-size:15px}
    .principle-note{padding:10px 12px;border-radius:12px;background:#121820;border:1px solid #2f3a46;font-size:12px;line-height:1.45;color:#c9d5e0}
    .principle-note b{color:#fff}
    .max-support-card{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:12px;border:1px solid #3a4552;border-bottom:3px solid var(--accent);background:#0a1016;text-decoration:none;color:inherit}
    .max-support-card:hover{border-color:var(--accent)}
    .max-support-card img{width:52px;height:52px;border-radius:8px;background:#fff;flex-shrink:0}
    .max-support-card b{display:block;font-size:13px;color:#fff;margin:0 0 2px}
    .max-support-card span{font-size:11px;color:var(--muted);line-height:1.4}
    .tour-compare{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0 4px}
    .tour-compare figure{margin:0}
    .tour-compare img{width:100%;height:88px;object-fit:cover;border-radius:8px;border:1px solid #3a4654;background:#05070a;display:block}
    .tour-compare figcaption{font-size:10px;color:var(--muted);margin-top:4px;text-align:center}
    .tour-demo-img{width:100%;max-height:120px;object-fit:cover;border-radius:8px;border:1px solid #3a4654;margin:8px 0 4px;display:block}
    .preview{width:100%;border-radius:10px;background:#05070a;border:1px solid var(--line);object-fit:contain;max-height:280px}
    .preview.lg{max-height:520px;min-height:280px}
    .tags{display:flex;flex-wrap:wrap;gap:6px}
    .tag{padding:4px 8px;border-radius:999px;background:#17202a;border:1px solid #2f3a46;font-size:12px;color:#c9d5e0}
    .meta{font-size:12px;color:var(--muted);line-height:1.4}
    .chat{flex:1;overflow:auto;display:flex;flex-direction:column;gap:8px;padding:4px;min-height:280px;max-height:55vh}
    .bubble{padding:8px 10px;border-radius:10px;max-width:95%;white-space:pre-wrap}
    .bubble.user{align-self:flex-end;background:#1c334d}
    .bubble.assistant{align-self:flex-start;background:#17202a;border:1px solid #2f3a46}
    .chat-input{display:flex;flex-direction:column;gap:8px}
    textarea{width:100%;min-height:72px;resize:vertical;border-radius:10px;border:1px solid var(--line);background:#090d12;color:var(--text);padding:10px;font:inherit}
    .quick{display:flex;flex-wrap:wrap;gap:6px}
    .quick button{font-size:12px;padding:7px 10px;transition:outline .15s,background .15s,border-color .15s,opacity .15s,transform .15s}
    .quick-group{display:none;flex-wrap:wrap;gap:6px;width:100%;padding:8px;border-radius:12px;border:1px dashed transparent;background:transparent}
    .quick-group.open{display:flex}
    .quick-group.for-brush{border-color:rgba(255,107,107,.45);background:rgba(255,70,70,.08)}
    .quick-group.for-eraser{border-color:rgba(79,209,197,.45);background:rgba(79,209,197,.08)}
    .quick-group .group-label{width:100%;font-size:11px;color:var(--muted);margin:0 0 2px}
    .quick button.lit-brush{background:rgba(255,70,70,.22);border-color:#ff6b6b;color:#ffd0d0;outline:2px solid rgba(255,107,107,.55);outline-offset:1px;transform:translateY(-1px)}
    .quick button.lit-eraser{background:rgba(79,209,197,.2);border-color:#4fd1c5;color:#c8fff8;outline:2px solid rgba(79,209,197,.55);outline-offset:1px;transform:translateY(-1px)}
    .quick button.dim{opacity:.38}
    .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .status{padding:8px 10px;border-radius:10px;background:#121820;border:1px solid #2a3340;font-size:12px}
    .status.busy{border-color:#f5b942;color:#f5d28a}
    .status.err{border-color:#c45;color:#f0a0a0}
    .hist{display:flex;gap:8px;overflow:auto;padding-bottom:4px}
    .hist img{width:72px;height:54px;object-fit:cover;border-radius:8px;border:1px solid var(--line);cursor:pointer}
    .hist-item{flex:0 0 auto;width:128px;border:1px solid var(--line);border-radius:10px;background:#0a1016;padding:5px;cursor:pointer;color:var(--muted);font-size:10px;text-align:left;position:relative}
    .hist-item.active{border-color:var(--accent);box-shadow:0 0 0 1px rgba(245,185,66,.35)}
    .hist-item .hist-thumb{position:relative;width:100%;height:62px;margin-bottom:4px;border-radius:6px;overflow:hidden;background:#030405}
    .hist-item .hist-thumb img{width:100%;height:100%;object-fit:cover;display:block;border:0;margin:0}
    .hist-item .hist-thumb .hist-ann{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none;mix-blend-mode:normal;opacity:.95}
    .hist-item .hist-markup-tag{margin-top:2px;color:#4fd1c5;font-weight:700}
    .hist-item span{display:block;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .sales-hint a.phone-copy{color:var(--accent);text-decoration:underline;cursor:pointer;border:0;background:none;font:inherit;padding:0}
    .sales-hint a.phone-copy:hover{color:#fff}
    .hist-item .hist-vote{margin-top:3px;font-weight:700;white-space:normal}
    .hist-item .hist-vote.like{color:#8fd48f}
    .hist-item .hist-vote.dislike{color:#e89a9a}
    .hist-item .hist-vote.pending{color:var(--accent)}
    .hist-item .hist-comment{margin-top:2px;white-space:normal;max-height:2.5em;overflow:hidden}
    .hist-hint{font-size:12px;color:var(--muted);margin:0}
    input[type=file]{width:100%;font:inherit;color:var(--muted)}
    .hidden{display:none!important}
    .dropzone{border:1.5px dashed #3a4654;border-radius:12px;padding:14px;background:#0a1016;cursor:pointer;transition:border-color .15s,background .15s;text-align:center}
    .dropzone:hover,.dropzone:focus{border-color:var(--accent);outline:none}
    .dropzone.dragover{border-color:var(--accent);background:#151c10}
    .dropzone.has-image{padding:8px;text-align:left}
    .dropzone .hint{font-size:13px;color:var(--muted);line-height:1.45}
    .dropzone .hint strong{color:var(--text);font-weight:700}
    .dropzone .hint kbd{display:inline-block;padding:1px 6px;border:1px solid #3a4654;border-radius:6px;background:#121820;font:12px Consolas,monospace;color:#d7e0ea}
    .dropzone .preview{max-height:220px;margin-top:8px;display:none}
    .dropzone.has-image .preview{display:block}
    .dropzone.has-image .hint{display:none}
    .drop-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}
    .result-stage{position:relative;border:1px solid var(--line);border-radius:12px;background:#030405;min-height:280px;max-height:520px;display:flex;align-items:center;justify-content:center;overflow:hidden}
    .result-stage img{max-width:100%;max-height:520px;width:auto;height:auto;object-fit:contain;border:0;border-radius:0;pointer-events:none;user-select:none}
    .result-stage canvas{position:absolute;left:0;top:0;touch-action:none;cursor:crosshair;z-index:2;pointer-events:none}
    .result-stage.is-editing canvas.tool-on{pointer-events:auto}
    .result-stage.is-editing{outline:2px solid #5a8fd4;outline-offset:1px}
    .markup-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
    .markup-bar .btn.active{outline:2px solid var(--accent);outline-offset:1px}
    .markup-bar .btn.active.brush{outline-color:#ff6b6b}
    .markup-bar .btn.active.eraser{outline-color:#4fd1c5}
    .markup-bar .brush-size{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
    .markup-bar .brush-size input{width:100px}
    .markup-next-step{display:none;margin-top:8px;padding:10px 12px;border:1px solid #3a6a78;border-radius:12px;background:#0d1a20;color:#d7eef4;font-size:13px;line-height:1.45}
    .markup-next-step.open{display:block;animation:niteosPulseBorder 1.4s ease-in-out 2}
    .markup-next-step b{color:#fff}
    .markup-next-step .step-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
    .chat-col.awaiting-instruction{border-color:#4fd1c5;box-shadow:0 0 0 2px rgba(79,209,197,.28);animation:niteosPulseBorder 1.4s ease-in-out 3}
    .chat-step-panel{display:none;padding:12px 14px;border-radius:14px;border:2px solid #4fd1c5;background:linear-gradient(180deg,#102428 0%,#0d1a20 100%);color:#e7f7fa;margin:0 0 10px}
    .chat-step-panel.open{display:block}
    .chat-step-panel .step-kicker{margin:0 0 4px;font-size:11px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#4fd1c5}
    .chat-step-panel h3{margin:0 0 8px;font-size:17px;color:#fff;line-height:1.3}
    .chat-step-panel ol{margin:0;padding-left:18px;color:#d7eef4;font-size:13px;line-height:1.55}
    .chat-step-panel ol b{color:#fff}
    .chat-step-panel .step-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
    .quick.awaiting{padding:10px;border-radius:14px;border:1px solid #3a6a78;background:#0a1418}
    .quick.awaiting .quick-empty-hint{display:none}
    .chat-input.needs-instruction{outline:2px solid #4fd1c5;outline-offset:2px;border-radius:12px}
    .chat-input.needs-instruction textarea{border-color:#4fd1c5;box-shadow:0 0 0 3px rgba(79,209,197,.18)}
    .chat-input .input-step-label{display:none;margin:0 0 4px;font-size:12px;font-weight:700;color:#4fd1c5}
    .chat-input.needs-instruction .input-step-label{display:block}
    .feedback-zone.blocking{border-color:#f5b942;box-shadow:0 0 0 3px rgba(245,185,66,.28)}
    .feedback-gate{position:fixed;inset:0;z-index:120;display:none;align-items:center;justify-content:center;padding:18px;background:rgba(2,6,10,.82)}
    .feedback-gate.open{display:flex}
    .feedback-gate-card{max-width:440px;width:100%;background:#101820;border:2px solid #f5b942;border-radius:18px;padding:22px 20px 18px;box-shadow:0 24px 60px rgba(0,0,0,.55);text-align:center}
    .feedback-gate-card h3{margin:0 0 8px;font-size:22px;color:#fff;line-height:1.25}
    .feedback-gate-card p{margin:0 0 16px;color:var(--muted);font-size:14px;line-height:1.5}
    .feedback-gate-card .gate-pending{margin:0 0 14px;padding:10px 12px;border-radius:10px;background:#1a2410;border:1px solid #3d5a20;color:#c8f0a0;font-size:13px;font-weight:700;line-height:1.4}
    .feedback-gate-card .gate-pending.hidden{display:none}
    .feedback-gate-card .gate-comment-wrap{margin:0 0 14px;text-align:left}
    .feedback-gate-card .gate-comment-wrap label{display:block;margin:0 0 6px;font-size:12px;color:var(--muted)}
    .feedback-gate-card .gate-comment-wrap textarea{width:100%;min-height:72px;resize:vertical;border-radius:10px;border:1px solid #3a4654;background:#090d12;color:var(--text);padding:10px;font:inherit}
    .feedback-gate-votes{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin:0 0 12px}
    .feedback-gate-votes .btn{min-width:140px;font-size:15px;font-weight:800;padding:12px 16px}
    .feedback-gate-votes .btn.like{border-color:#3d8f5a;background:#1f3d2a;color:#c8f0d4}
    .feedback-gate-votes .btn.dislike{border-color:#c45;background:#3d1f24;color:#f0c0c0}
    .feedback-gate-votes .btn:disabled{opacity:.55;cursor:wait}
    .feedback-gate-status{min-height:18px;margin:0 0 8px;font-size:13px;color:var(--accent)}
    .feedback-gate-status.err{color:#f0a0a0}
    .feedback-gate-cancel{border:0;background:transparent;color:#8d97a3;font:inherit;font-size:13px;cursor:pointer;text-decoration:underline;padding:6px}
    .feedback-gate-cancel:hover{color:#c9d5e0}
    @keyframes niteosPulseBorder{0%,100%{box-shadow:0 0 0 0 rgba(79,209,197,.0)}50%{box-shadow:0 0 0 4px rgba(79,209,197,.25)}}
    .legend{font-size:12px;color:var(--muted);line-height:1.45}
    .legend b.red,.principle-note b.red{color:#ff6b6b}
    .legend b.cyan,.principle-note b.cyan{color:#4fd1c5}
    .help-btn-promo{border:0;border-radius:10px;padding:10px 14px;font:inherit;font-weight:800;cursor:pointer;background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;text-decoration:none;display:inline-flex;align-items:center}
    .tour-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:90;display:none;align-items:center;justify-content:center;padding:18px}
    .tour-backdrop.open{display:flex}
    .tour-modal{max-width:480px;width:100%;background:#0f151c;border:1px solid #2b333d;border-radius:16px;padding:18px;box-shadow:0 20px 50px rgba(0,0,0,.45)}
    .tour-modal h3{margin:0 0 8px;font-size:18px}
    .tour-modal p{margin:0 0 10px;color:var(--muted);line-height:1.5}
    .tour-modal ol{margin:0 0 14px;padding-left:18px;color:#dbe4ee;line-height:1.55}
    .tour-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
    .coach-root{position:fixed;inset:0;z-index:110;display:none;pointer-events:none}
    .coach-root.open{display:block;pointer-events:none}
    .coach-shade{position:absolute;inset:0;background:rgba(3,6,10,.78);pointer-events:none}
    .coach-hole{position:absolute;border-radius:14px;box-shadow:0 0 0 9999px rgba(3,6,10,.78),0 0 0 3px rgba(245,185,66,.95),0 0 28px rgba(245,185,66,.35);pointer-events:none;transition:top .2s,left .2s,width .2s,height .2s}
    .coach-card{position:fixed;z-index:112;width:min(400px,calc(100vw - 24px));background:#101820;border:1px solid #3a4654;border-radius:16px;padding:14px 14px 12px;box-shadow:0 18px 40px rgba(0,0,0,.5);color:var(--text);pointer-events:auto}
    .coach-card .step-n{font-size:11px;color:var(--accent);font-weight:800;letter-spacing:.04em;margin:0 0 4px;text-transform:uppercase}
    .coach-card h3{margin:0 0 6px;font-size:16px}
    .coach-card p{margin:0 0 10px;color:var(--muted);font-size:13px;line-height:1.5}
    .coach-card ol{margin:0 0 12px;padding-left:18px;color:#dbe4ee;font-size:13px;line-height:1.5}
    .coach-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
    .tour-pulse{animation:tourPulse 1.2s ease-in-out infinite}
    @keyframes tourPulse{0%,100%{box-shadow:0 0 0 0 rgba(245,185,66,.55)}50%{box-shadow:0 0 0 8px rgba(245,185,66,0)}}
    .tour-target-live{position:relative;z-index:91!important}
    .busy-overlay.tour-demo{z-index:100;pointer-events:none}
    .feedback-zone{border:1px solid var(--line);border-radius:14px;padding:12px;background:#0a1016;display:none;flex-direction:column;gap:8px}
    .feedback-zone.open{display:flex}
    .feedback-zone.required{border-color:var(--accent);box-shadow:0 0 0 2px rgba(245,185,66,.22)}
    .feedback-votes{display:flex;gap:8px;flex-wrap:wrap}
    .feedback-votes button.active.like{background:#1f3d2a;border-color:#3d8f5a;color:#c8f0d4}
    .feedback-votes button.active.dislike{background:#3d1f24;border-color:#c45;color:#f0c0c0}
    .feedback-zone select,.feedback-zone input{width:100%;border-radius:10px;border:1px solid var(--line);background:#090d12;color:var(--text);padding:10px;font:inherit}
    .feedback-toast{position:fixed;right:16px;bottom:88px;z-index:80;width:min(320px,calc(100vw - 28px));background:rgba(12,16,22,.96);border:1px solid #3a4552;border-radius:14px;padding:14px;box-shadow:0 12px 36px rgba(0,0,0,.45)}
    .feedback-toast.hidden{display:none}
    .feedback-toast-title{margin:0 0 4px;font-size:15px;font-weight:700}
    .feedback-toast-lead{margin:0 0 10px;font-size:12px;color:var(--muted);line-height:1.45}
    .feedback-toast-actions{display:flex;gap:8px;flex-wrap:wrap}
    .feedback-toast-close{position:absolute;top:8px;right:10px;border:0;background:transparent;color:#8d97a3;font-size:18px;cursor:pointer}
    .busy-overlay{position:fixed;inset:0;background:rgba(4,8,12,.72);z-index:95;display:none;align-items:center;justify-content:center;padding:18px}
    .busy-overlay.open{display:flex}
    .busy-modal{max-width:420px;width:100%;background:#0f151c;border:1px solid #3a4654;border-radius:16px;padding:22px 20px;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,.5)}
    .busy-modal h3{margin:0 0 8px;font-size:18px;color:var(--text)}
    .busy-modal p{margin:0;color:var(--muted);line-height:1.5}
    .busy-spinner{width:36px;height:36px;margin:0 auto 14px;border:3px solid #2b333d;border-top-color:var(--accent);border-radius:50%;animation:niteosSpin .8s linear infinite}
    @keyframes niteosSpin{to{transform:rotate(360deg)}}
    .card-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
    .tip{position:relative;display:inline-flex;align-items:center;vertical-align:middle}
    .tip-btn{width:22px;height:22px;border-radius:999px;border:1px solid #3a4654;background:#151c26;color:#c9d5e0;font:700 12px/1 Segoe UI,Arial,sans-serif;cursor:pointer;padding:0}
    .tip-btn:hover,.tip.open .tip-btn{border-color:var(--accent);color:var(--accent)}
    .tip-bubble{display:none;position:absolute;z-index:40;left:0;top:calc(100% + 8px);width:min(280px,70vw);background:#101820;border:1px solid #3a4654;border-radius:12px;padding:10px 12px;color:#dbe4ee;font-size:12px;line-height:1.45;box-shadow:0 12px 28px rgba(0,0,0,.4)}
    .tip.open .tip-bubble{display:block}
    .tip-bubble.right{left:auto;right:0}
    .photo-checklist{margin:0;padding-left:18px;color:#dbe4ee;line-height:1.55;font-size:13px}
    .photo-checklist li{margin:0 0 6px}
    .warn-note{padding:10px 12px;border-radius:10px;background:#1a1510;border:1px solid #5a4630;color:#f0d2a0;font-size:12px;line-height:1.45}
    .guide-strip{display:flex;flex-wrap:wrap;gap:8px;padding:10px 12px;border-radius:12px;background:#0a1016;border:1px dashed #3a4654;font-size:12px;color:var(--muted);line-height:1.4}
    .guide-strip b{color:var(--text)}
    .guide-step{flex:1 1 140px;min-width:120px}
    .tour-ghost-cursor{position:fixed;z-index:113;width:16px;height:16px;border-radius:50% 0 50% 50%;background:var(--accent);pointer-events:none;transform:rotate(-35deg);box-shadow:0 2px 10px rgba(0,0,0,.45);opacity:0;transition:top .45s ease,left .45s ease,opacity .2s}
    .tour-ghost-cursor.on{opacity:1}
    .tour-action-chip{display:inline-flex;align-items:center;gap:6px;margin:0 0 8px;padding:5px 10px;border-radius:999px;background:#1a2410;border:1px solid #3d5a20;color:#c8f0a0;font-size:11px;font-weight:700}
    .tour-compare.live{position:relative}
    .tour-compare.live figure{position:relative}
    .tour-morph{position:relative;width:100%;height:110px;border-radius:8px;overflow:hidden;border:1px solid #3a4654;background:#05070a;margin:8px 0}
    .tour-morph img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
    .tour-morph img.after{opacity:0;animation:tourMorph 2.4s ease-in-out infinite alternate}
    @keyframes tourMorph{0%,35%{opacity:0}65%,100%{opacity:1}}
    .tour-morph .labels{position:absolute;left:8px;bottom:8px;z-index:2;display:flex;gap:6px}
    .tour-morph .labels span{font-size:10px;font-weight:700;padding:2px 7px;border-radius:6px;background:rgba(0,0,0,.65);color:#fff}
    .dropzone.tour-demo-flash{border-color:var(--accent)!important;background:#151c10!important;animation:tourPulse 1s ease-in-out 2}
    .btn.tour-click-flash{animation:tourClickFlash .7s ease 2}
    @keyframes tourClickFlash{0%,100%{filter:none}40%{filter:brightness(1.25);transform:scale(1.04)}}
    .result-stage.tour-playing{outline:2px solid var(--accent);outline-offset:1px}
    .zone-intent-overlay{position:fixed;inset:0;z-index:98;display:none;align-items:flex-end;justify-content:center;padding:16px;background:rgba(4,8,12,.45);backdrop-filter:blur(2px)}
    .zone-intent-overlay.open{display:flex}
    .zone-intent-card{width:min(460px,100%);background:#101820;border:1px solid #3a4654;border-radius:16px;padding:16px;box-shadow:0 18px 48px rgba(0,0,0,.5);margin-bottom:max(12px,env(safe-area-inset-bottom))}
    .zone-intent-card h3{margin:0 0 6px;font-size:17px;color:var(--text)}
    .zone-intent-card .lead{margin:0 0 12px;font-size:13px;color:var(--muted);line-height:1.45}
    .zone-intent-presets{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
    .zone-intent-presets .btn{font-size:12px;padding:8px 10px}
    .zone-intent-card textarea{width:100%;min-height:78px;border-radius:10px;border:1px solid var(--line);background:#090d12;color:var(--text);padding:10px;font:inherit;resize:vertical}
    .zone-intent-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
    .zone-intent-actions .btn{flex:1 1 120px}
  </style>
</head>
<body>
{{MAX_GROUP_WIDGET}}
<div class="busy-overlay" id="busyOverlay" aria-live="polite">
  <div class="busy-modal">
    <div class="busy-spinner" aria-hidden="true"></div>
    <h3 id="busyTitle">Идёт генерация</h3>
    <p id="busyText">Подождите, агент обрабатывает запрос…</p>
  </div>
</div>
<div class="zone-intent-overlay" id="zoneIntentOverlay" role="dialog" aria-modal="true" aria-labelledby="zoneIntentTitle">
  <div class="zone-intent-card">
    <h3 id="zoneIntentTitle">Что сделать с этой зоной?</h3>
    <p class="lead" id="zoneIntentLead">Зона отмечена на фото. Выберите действие или напишите своими словами — отправим правку сразу отсюда.</p>
    <div class="zone-intent-presets" id="zoneIntentPresets">
      <button type="button" class="btn secondary" data-intent="remove" onclick="pickZoneIntent('убери ТОЛЬКО отмеченные светильники и лучи в этой зоне, остальные не трогай; стену восстанови как у соседних панелей')">Убрать свет</button>
      <button type="button" class="btn secondary" data-intent="place" onclick="pickZoneIntent('проставь прожектор X-RAY только в отмеченной зоне, размер корпуса как у соседних архитектурных прожекторов, луч реалистичный; остальной фасад не трогай')">Поставить прожектор</button>
      <button type="button" class="btn secondary" data-intent="linear" onclick="pickZoneIntent('проставь линейный светильник MAGISTRAL только в отмеченной зоне по архитектурной линии; остальной фасад не трогай')">Поставить линейный</button>
      <button type="button" class="btn secondary" data-intent="change" onclick="pickZoneIntent('измени ТОЛЬКО отмеченные светильники в этой зоне, остальные не трогай')">Изменить</button>
      <button type="button" class="btn secondary" data-intent="warmer" onclick="pickZoneIntent('сделай отмеченные лучи теплее и мягче, остальные светильники не трогай')">Теплее</button>
    </div>
    <label class="muted" for="zoneIntentInput" style="display:block;margin:0 0 6px;font-size:12px">Или напишите сами:</label>
    <textarea id="zoneIntentInput" placeholder="Например: сюда прожектор у входа; убери верхний луч…"></textarea>
    <div class="zone-intent-actions">
      <button type="button" class="btn secondary" onclick="closeZoneIntentPanel(false)">Ещё рисую</button>
      <button type="button" class="btn secondary" onclick="clearEditMarkup(); closeZoneIntentPanel(true)">Сбросить зону</button>
      <button type="button" class="btn accent" id="zoneIntentSendBtn" onclick="submitZoneIntent()">Отправить правку</button>
    </div>
  </div>
</div>
<div class="tour-backdrop" id="photoCheckModal" role="dialog" aria-label="Проверка фото перед генерацией">
  <div class="tour-modal">
    <h3>Проверьте фото перед генерацией</h3>
    <p>Лучше всего подходит <b style="color:#eef2f6">дневной фронтальный снимок фасада</b> без лишнего.</p>
    <ul class="photo-checklist">
      <li>Нет чужих надписей, водяных знаков, стрелок и рамок поверх здания</li>
      <li>Фасад целиком в кадре, без сильного наклона и сильных бликов</li>
      <li>Не ночной уже готовый рендер — исходник лучше дневной</li>
      <li>Без людей/машин на переднем плане, закрывающих стены</li>
    </ul>
    <div class="warn-note" style="margin:12px 0">Если на фото есть надписи или чужой водяной знак — лучше загрузить чистое фото. Иначе агент может сохранить их в результате.</div>
    <div class="tour-actions">
      <button type="button" class="btn secondary" onclick="closePhotoCheck()">Отмена</button>
      <button type="button" class="btn secondary" onclick="closePhotoCheck(); document.getElementById('pickFileBtn').click()">Другое фото</button>
      <button type="button" class="btn accent" onclick="confirmPhotoCheckAndStart()">Всё ок, генерировать</button>
    </div>
  </div>
</div>
<header>
  <div>
    <a class="btn secondary" href="/" id="backHomeBtn" style="margin-bottom:8px">← Назад на главную</a>
    <h1>AI-студия · Vision Agent</h1>
    <div class="muted" id="projectLabel">Новый проект</div>
  </div>
  <div class="header-actions row">
    <!-- К шаблонам временно скрыто
    <a class="btn secondary" href="/dealer" id="dealerLink">К шаблонам</a>
    <a class="btn secondary" href="/video" id="videoLink">Видео</a>
    -->
    <div class="sales-hint">Хотите узнать подробнее о цене этой концепции — номер <a href="#" class="phone-copy" id="contactPhoneLink" data-phone="8 843 202 21 39" onclick="return copyContactPhone(event)">8 843 202 21 39</a> <span class="muted" id="phoneCopyHint" style="display:none">скопировано</span></div>
    <button type="button" class="help-btn-promo" id="helpBtnPromo" onclick="openStudioTour()">Как это работает?</button>
    <button class="btn secondary" id="newProjectTour" onclick="createProject()">Новый проект</button>
  </div>
</header>

<div class="tour-backdrop" id="studioTour" role="dialog" aria-label="Обучение AI-студии" style="display:none">
  <!-- Legacy modal kept unused; interactive coach tour is primary -->
  <div class="tour-modal">
    <h3 id="tourTitle">Как работает AI-агент</h3>
    <div id="tourBody"></div>
    <div class="tour-actions">
      <button type="button" class="btn secondary" id="tourPrevBtn" onclick="prevStudioTour()">← Назад</button>
      <button type="button" class="btn secondary" onclick="closeStudioTour()">Закрыть</button>
      <button type="button" class="btn accent" id="tourNextBtn" onclick="nextStudioTour()">Далее →</button>
    </div>
  </div>
</div>
<div class="coach-root" id="coachRoot" aria-live="polite">
  <div class="coach-shade" id="coachShade" onclick="/* keep open */"></div>
  <div class="coach-hole" id="coachHole"></div>
  <div class="coach-card" id="coachCard">
    <div class="step-n" id="coachStepN">Шаг 1 из 8</div>
    <h3 id="coachTitle">Заголовок</h3>
    <div id="coachBody"></div>
    <div class="coach-actions">
      <button type="button" class="btn secondary" id="coachPrevBtn" onclick="prevStudioTour()">← Назад</button>
      <button type="button" class="btn secondary" onclick="closeStudioTour()">Закрыть</button>
      <button type="button" class="btn accent" id="coachNextBtn" onclick="nextStudioTour()">Далее →</button>
    </div>
  </div>
</div>

<div class="feedback-gate" id="feedbackGate" role="dialog" aria-modal="true" aria-labelledby="feedbackGateTitle">
  <div class="feedback-gate-card">
    <h3 id="feedbackGateTitle">Поставьте оценку</h3>
    <p id="feedbackGateLead">Без оценки нельзя продолжить: ни генерацию, ни правку, ни новый проект.</p>
    <div class="gate-pending hidden" id="feedbackGatePending">После оценки сразу продолжим ваш запрос.</div>
    <div class="gate-comment-wrap">
      <label for="feedbackGateComment">Комментарий <span style="font-weight:400">(необязательно)</span></label>
      <textarea id="feedbackGateComment" placeholder="Что понравилось или что улучшить — по желанию"></textarea>
    </div>
    <div class="feedback-gate-votes">
      <button type="button" class="btn like" id="feedbackGateLikeBtn" onclick="submitFeedbackFromGate('like')">Нравится</button>
      <button type="button" class="btn dislike" id="feedbackGateDislikeBtn" onclick="submitFeedbackFromGate('dislike')">Не нравится</button>
    </div>
    <div class="feedback-gate-status" id="feedbackGateStatus"></div>
    <button type="button" class="feedback-gate-cancel" id="feedbackGateCancelBtn" onclick="cancelFeedbackGate()">Отмена — вернуться назад</button>
  </div>
</div>
<div class="feedback-toast hidden" id="feedbackToast" role="status" aria-label="Напоминание об оценке" style="display:none!important" aria-hidden="true">
  <!-- legacy toast kept hidden; blocking gate modal is used instead -->
</div>
<main class="layout">
  <section class="card">
    <div class="card-head">
      <h2>1. Фото фасада</h2>
      <span class="tip" id="tipSource">
        <button type="button" class="tip-btn" onclick="toggleTip('tipSource')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Сюда загружается исходное фото здания. Дважды нажмите зону, вставьте Ctrl+V или «Выбрать файл». Референс освещения подбирается скрыто — на экране не показывается.</span>
      </span>
    </div>
    <div class="guide-strip" id="guideStrip">
      <div class="guide-step"><b>Шаг 1</b><br>Загрузите дневное фото фасада</div>
      <div class="guide-step"><b>Шаг 2</b><br>«Анализ → генерация»</div>
      <div class="guide-step"><b>Шаг 3</b><br>Текст в чате · кисть/ластик для точности</div>
    </div>
    <div class="dropzone" id="dropzone" tabindex="0" role="button" aria-label="Вставить или загрузить фото фасада">
      <div class="hint">
        <strong>Вставьте фото фасада</strong><br>
        Ctrl+V / Cmd+V · перетащите файл · или дважды нажмите сюда<br>
        <span style="opacity:.85">Лучше дневной фронтальный снимок без надписей и водяных знаков</span>
      </div>
      <img class="preview" id="sourceImg" alt="source">
    </div>
    <input type="file" id="sourceFile" class="hidden" accept="image/*">
    <div class="drop-actions">
      <button type="button" class="btn secondary" id="pickFileBtn" title="Открыть выбор файла с диска">Выбрать файл</button>
      <button type="button" class="btn accent" id="startBtn" onclick="startStudio()" disabled title="Сначала загрузите фото">Анализ → генерация</button>
      <span class="tip" id="tipStart">
        <button type="button" class="tip-btn" onclick="toggleTip('tipStart')" aria-label="Подсказка">?</button>
        <span class="tip-bubble">Перед запуском появится проверка фото. Агент сам подберёт стиль света и сделает ночной рендер.</span>
      </span>
    </div>
    <div class="status" id="statusBox">Скопируйте фото и нажмите Ctrl+V — или выберите файл</div>
    <div class="warn-note" id="photoSoftWarn">Перед генерацией: уберите с фото чужие надписи/водяные знаки или загрузите чистое фото фасада — так результат будет чище.</div>
  </section>

  <section class="card work-col" id="resultCard">
    <div class="col-kicker work">Рабочая зона · фото и разметка</div>
    <div class="card-head">
      <h2>2. Результат</h2>
      <span class="tip" id="tipResult">
        <button type="button" class="tip-btn" onclick="toggleTip('tipResult')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Здесь появляется ночной рендер. Кисть (красная) — изменить/проставить свет в зоне. Ластик (голубой) — убрать светильник. Затем обязательно напишите задачу в чате и нажмите «Отправить».</span>
      </span>
    </div>
    <div class="result-stage" id="resultStage">
      <img id="finalImg" alt="final">
      <canvas id="editMarkupCanvas" class="hidden" tabindex="0" aria-hidden="true"></canvas>
    </div>
    <div class="markup-bar" id="markupBarTour">
      <button type="button" class="btn secondary brush" id="editBrushBtn" onclick="toggleEditTool('brush')" title="Красная кисть: изменить или проставить свет">Кисть · правка</button>
      <button type="button" class="btn secondary eraser" id="editEraserBtn" onclick="toggleEditTool('eraser')" title="Голубой ластик: убрать светильник">Ластик · убрать</button>
      <label class="brush-size">Толщина <input type="range" id="editBrushSize" min="4" max="48" value="16" oninput="updateEditBrushSize(this.value)"></label>
      <button type="button" class="btn secondary" onclick="clearEditMarkup()" title="Стереть разметку и выключить инструменты">Очистить разметку</button>
      <span class="tip" id="tipBrush">
        <button type="button" class="tip-btn" onclick="toggleTip('tipBrush')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Инструменты включаются повторным нажатием. Без текста в чате правка не отправится.</span>
      </span>
    </div>
    <div class="principle-note" id="workPrinciple">
      <b>Главное:</b> правки можно описать просто текстом в чате справа.
      <b class="red">Кисть</b> и <b class="cyan">ластик</b> — для точности: отметить зону и аккуратно поменять только её.
      Можно разметить сразу и красным, и голубым, затем нажать готовые кнопки в чате.
    </div>
    <div class="legend">
      1) Включите <b class="red">кисть</b> и/или <b class="cyan">ластик</b>, отметьте зону на фото.
      2) Сразу откроется окно: <b>что сделать с этим местом?</b> — шаблон или свой текст.
      3) «Отправить правку» прямо из окна. Краска в финале не останется.
      4) Без разметки по-прежнему можно править только текстом в чате.
    </div>
    <div class="status" id="markupHint" style="display:none;margin-top:4px">Что хотите изменить на отмеченных светильниках? Напишите в чат ниже.</div>
    <div class="markup-next-step" id="markupNextStep" role="status">
      <b>Зона отмечена.</b> Дальше смотрите <b>чат справа</b>: шаблоны или свой текст → «Отправить».
      <div class="step-actions">
        <button type="button" class="btn accent" onclick="revealChatStepPanel(true)">Открыть чат и шаблоны</button>
      </div>
    </div>
    <div class="row">
      <button class="btn secondary" onclick="downloadFinal()" id="downloadBtn" disabled title="Скачать текущий результат">Скачать</button>
      <button class="btn secondary" onclick="copyFinal()" id="copyFinalBtn" disabled title="Скопировать результат в буфер">Копировать</button>
      <span class="tip" id="tipCopy">
        <button type="button" class="tip-btn" onclick="toggleTip('tipCopy')" aria-label="Подсказка">?</button>
        <span class="tip-bubble">«Копировать» — в буфер. Ctrl+V без результата грузит исходник; с результатом — вставляет копию как рабочее фото.</span>
      </span>
    </div>
    <div class="muted" style="font-size:12px">Ctrl+V: без результата — в источник; с результатом — вставить копию как рабочее фото для правок.</div>
    <div class="card-head" style="margin-top:4px">
      <div class="muted">История версий · клик = сделать активной для правок</div>
      <span class="tip" id="tipHistory">
        <button type="button" class="tip-btn" onclick="toggleTip('tipHistory')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Клик по миниатюре делает эту версию активной. Дальше кисть/чат правят именно её.</span>
      </span>
    </div>
    <p class="hist-hint" id="activeHistoryHint"></p>
    <div class="hist" id="historyStrip"></div>
  </section>

  <section class="card chat-col" id="chatCard">
    <div class="col-kicker chat-label">Чат · команды и готовые кнопки</div>
    <div class="card-head">
      <h2>3. Чат с агентом</h2>
      <span class="tip" id="tipChat">
        <button type="button" class="tip-btn" onclick="toggleTip('tipChat')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Текст всегда работает сам. Кисть/ластик только уточняют где менять. Готовые кнопки можно нажимать по очереди — текст добавится в поле.</span>
      </span>
    </div>
    <div class="chat-step-panel" id="chatStepPanel" role="status">
      <div class="step-kicker" id="chatStepKicker">Шаг 2 из 2</div>
      <h3 id="chatStepTitle">Зона отмечена — что сделать?</h3>
      <ol id="chatStepList">
        <li><b>Нажмите шаблон</b> ниже — текст сам попадёт в поле</li>
        <li>или <b>напишите сами</b> в поле внизу</li>
        <li>затем нажмите <b>«Отправить»</b></li>
      </ol>
      <div class="step-actions">
        <button type="button" class="btn accent" onclick="scrollToQuickTemplates()">К шаблонам</button>
        <button type="button" class="btn secondary" onclick="focusChatInstruction()">Написать свой текст</button>
      </div>
    </div>
    <div class="principle-note" id="chatIdleNote">Без разметки достаточно написать задачу своими словами и нажать «Отправить». Кисть/ластик слева — если нужно указать точное место.</div>
    <div class="quick" id="quickPrompts">
      <div class="quick-group for-eraser" id="quickEraserGroup">
        <div class="group-label">Шаблоны ластика (голубая зона) — нажмите одну кнопку:</div>
        <button type="button" class="btn secondary lit-eraser" data-tool="eraser" onclick="fillChatPrompt('убери ТОЛЬКО отмеченные голубым светильники и лучи, все остальные светильники оставь как есть')" title="Убрать отмеченные светильники">Убери отмеченное</button>
        <button type="button" class="btn secondary lit-eraser" data-tool="eraser" onclick="fillChatPrompt('убери отмеченные голубым прожекторы и их лучи, стену оставь как у соседних панелей без затемнения')" title="Убрать прожекторы в зоне">Убери прожекторы</button>
        <button type="button" class="btn secondary lit-eraser" data-tool="eraser" onclick="fillChatPrompt('ослабь или почти погаси только отмеченные голубым лучи, сами соседние светильники не трогай')" title="Ослабить свет в зоне">Ослабь лучи</button>
      </div>
      <div class="quick-group for-brush" id="quickBrushGroup">
        <div class="group-label">Шаблоны кисти (красная зона) — нажмите одну кнопку:</div>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('измени ТОЛЬКО отмеченные красным светильники, остальные не трогай')" title="Изменить отмеченное">Измени отмеченное</button>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('проставь прожектор только в красной отмеченной зоне, остальные светильники не трогай')" title="Проставить прожектор">Проставь прожектор</button>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('сделай отмеченные красным лучи теплее и мягче, остальные светильники не трогай')" title="Теплее в зоне">Теплее в зоне</button>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('усилить яркость только отмеченных красным светильников и лучей, остальное не трогай')" title="Ярче в зоне">Ярче в зоне</button>
      </div>
      <div class="group-label" id="quickAnyLabel" style="width:100%;font-size:11px;color:var(--muted)">Общие команды (без разметки тоже можно):</div>
      <button type="button" class="btn secondary" data-tool="any" onclick="fillChatPrompt('теплее')" title="Подставить текст «теплее»">Теплее</button>
      <button type="button" class="btn secondary" data-tool="any" onclick="fillChatPrompt('усиль карниз')" title="Подставить текст про карниз">Усиль карниз</button>
    </div>
    <div class="chat-input" id="chatSendTour">
      <div class="input-step-label" id="chatInputStepLabel">Сюда напишите, что сделать с отмеченным — или сначала нажмите шаблон выше</div>
      <textarea id="chatInput" placeholder="Можно просто написать: убери левый / сделай теплее / проставь прожектор у входа…"></textarea>
      <button class="btn accent" id="chatBtn" onclick="sendChat()" disabled title="Отправить правку агенту">Отправить</button>
    </div>
    <div class="chat" id="chatBox"></div>
    <a class="max-support-card" id="maxSupportCard" href="{{MAX_GROUP_JOIN_URL}}" target="_blank" rel="noopener noreferrer">
      <img src="{{MAX_GROUP_QR_URL}}" width="52" height="52" alt="QR MAX" loading="lazy">
      <div>
        <b>Поддержка</b>
        <span>Сюда можно кидать скрины результата, писать вопросы и предложения — ответим в группе MAX.</span>
      </div>
    </a>
    <section class="feedback-zone" id="feedbackZone">
      <h2 style="margin:0;font-size:15px" id="feedbackTitle">Оценка этой генерации</h2>
      <p class="muted" id="feedbackLead" style="margin:0">Подробный отзыв необязателен. Если нажмёте генерацию без оценки — поверх экрана откроется окно «Поставьте оценку».</p>
      <div class="feedback-votes" id="feedbackVotes">
        <button type="button" class="btn secondary like" id="feedbackLikeBtn" onclick="setFeedbackVote('like')">Нравится</button>
        <button type="button" class="btn secondary dislike" id="feedbackDislikeBtn" onclick="setFeedbackVote('dislike')">Не нравится</button>
      </div>
      <select id="feedbackIssue" aria-label="Что улучшить">
        <option value="">Что улучшить (необязательно)</option>
        <option value="placement_incorrect">Расстановка света</option>
        <option value="coverage_incomplete">Не хватает покрытия</option>
        <option value="overlit">Слишком ярко</option>
        <option value="underlit">Мало света</option>
        <option value="style_mismatch">Не тот стиль</option>
        <option value="other">Другое</option>
      </select>
      <textarea id="feedbackComment" placeholder="Комментарий (необязательно)" style="min-height:64px"></textarea>
      <input id="feedbackContact" type="text" placeholder="Email или телефон (необязательно)">
      <button type="button" class="btn accent" onclick="submitFeedback()" id="feedbackSubmitBtn">Отправить отзыв</button>
      <div class="muted" id="feedbackStatus"></div>
    </section>
  </section>
</main>
<script>
let projectId = '';
let busy = false;
let lastState = {};
let editDrawing = false;
let editLastPoint = null;
let editTool = null; // 'brush' | 'eraser' | null (off)
let editBrushSize = 16;
let editMarkupReady = false;
let markupBound = false;
let feedbackVote = '';
let feedbackTimer = null;
let feedbackPromptedHistoryId = '';
let feedbackToastDismissedFor = '';
let pendingAfterFeedback = null; // {type:'generate'|'chat'|'createProject'}
let studioImageModel = '';
const FEEDBACK_TOAST_DELAY_MS = 8000;
let markupUsedBrush = false;
let markupUsedEraser = false;
let tourStep = 0;
let tourActive = false;
let tourResizeBound = false;
let tourTimers = [];
let tourSnapshot = null;
let tourActionKey = '';
let tourLayoutTimer = null;
const TOUR_BEFORE = '/assets/studio_tour/before.png';
const TOUR_AFTER = '/assets/studio_tour/after.png';
const STUDIO_TOUR = [
  {
    title: 'Что получите',
    target: 'resultStage',
    place: 'below',
    action: 'beforeAfter',
    html: '<div class="tour-action-chip">▶ Смотрите превращение</div><div class="tour-morph"><img src="'+TOUR_BEFORE+'" alt="до"><img class="after" src="'+TOUR_AFTER+'" alt="после"><div class="labels"><span>До</span><span>После</span></div></div><p>Дневное фото → ночная концепция подсветки NITEOS. Дальше — сами действия на экране.</p>'
  },
  {
    title: 'Действие: загрузка фото',
    target: 'dropzone',
    place: 'below',
    action: 'upload',
    html: '<div class="tour-action-chip">▶ Вставляем фото в зону</div><p>Курсор показывает, как фото попадает в окно слева.</p><ol><li><b>Ctrl+V</b> / перетащить / дважды клик</li><li>Лучше дневной фронтальный снимок</li></ol>'
  },
  {
    title: 'Действие: генерация',
    target: 'startBtn',
    place: 'below',
    action: 'generate',
    html: '<div class="tour-action-chip">▶ Жмём «Анализ → генерация»</div><p>Кнопка мигает, затем короткое демо окна ожидания — так выглядит реальный запуск.</p>'
  },
  {
    title: 'Действие: результат',
    target: 'resultCard',
    place: 'below',
    action: 'result',
    html: '<div class="tour-action-chip">▶ Результат в центре</div><p>Ночной рендер появляется здесь. Можно <b>Скачать</b> файл или <b>Копировать</b> в буфер.</p>'
  },
  {
    title: 'Действие: кисть и ластик',
    target: 'resultCard',
    place: 'below',
    action: 'markup',
    html: '<div class="tour-action-chip">▶ Рисуем зоны на фото</div><p>Смотрите на результат: сначала красная кисть, затем голубой ластик — как при живой правке.</p><ol><li><b style="color:#ff6b6b">Кисть</b> — изменить / добавить свет</li><li><b style="color:#4fd1c5">Ластик</b> — убрать / ослабить</li></ol>'
  },
  {
    title: 'Действие: чат и кнопки',
    target: 'chatCard',
    place: 'above',
    action: 'chat',
    html: '<div class="tour-action-chip">▶ Пишем задачу в чат</div><p>Текст набирается сам, готовые кнопки подставляют команды. Можно править <b>только текстом</b> — кисть нужна для точности «где».</p>'
  },
  {
    title: 'Действие: поддержка',
    target: 'maxSupportCard',
    place: 'above',
    action: 'max',
    html: '<div class="tour-action-chip">▶ Поддержка</div><p>Скрины, вопросы и предложения — в блок <b>Поддержка</b> (QR справа внизу и карточка в чате).</p>'
  },
  {
    title: 'Готово',
    target: 'helpBtnPromo',
    place: 'below',
    action: 'done',
    html: '<div class="tour-action-chip">✓ Можно начинать</div><p>Тур всегда открывается кнопкой <b>«Как это работает?»</b>. Создайте проект и загрузите своё фото.</p>'
  }
];

function tourDelay(fn, ms){
  const id = setTimeout(fn, ms);
  tourTimers.push(id);
  return id;
}
function clearTourTimers(){
  tourTimers.forEach(clearTimeout);
  tourTimers = [];
}
function ensureTourCursor(){
  let el = document.getElementById('tourGhostCursor');
  if(!el){
    el = document.createElement('div');
    el.id = 'tourGhostCursor';
    el.className = 'tour-ghost-cursor';
    document.body.appendChild(el);
  }
  return el;
}
function moveTourCursorTo(el, on){
  const cur = ensureTourCursor();
  if(!el){ cur.classList.remove('on'); return; }
  const r = el.getBoundingClientRect();
  cur.style.left = (r.left + r.width * 0.55) + 'px';
  cur.style.top = (r.top + r.height * 0.55) + 'px';
  cur.classList.toggle('on', !!on);
}
function snapshotTourUi(){
  const sourceImg = document.getElementById('sourceImg');
  const finalImg = document.getElementById('finalImg');
  const dropzone = document.getElementById('dropzone');
  const chatInput = document.getElementById('chatInput');
  const canvas = document.getElementById('editMarkupCanvas');
  let markupData = '';
  try{
    if(canvas && canvas.width && canvas.height) markupData = canvas.toDataURL('image/png');
  }catch(_){}
  return {
    sourceSrc: sourceImg ? sourceImg.getAttribute('src') : '',
    finalSrc: finalImg ? finalImg.getAttribute('src') : '',
    dropHas: dropzone ? dropzone.classList.contains('has-image') : false,
    chatVal: chatInput ? chatInput.value : '',
    editTool,
    markupUsedBrush,
    markupUsedEraser,
    markupData,
  };
}
function restoreTourUi(){
  if(!tourSnapshot) return;
  const sourceImg = document.getElementById('sourceImg');
  const finalImg = document.getElementById('finalImg');
  const dropzone = document.getElementById('dropzone');
  const chatInput = document.getElementById('chatInput');
  if(sourceImg){
    if(tourSnapshot.sourceSrc) sourceImg.src = tourSnapshot.sourceSrc;
    else { sourceImg.removeAttribute('src'); sourceImg.src = ''; }
  }
  if(dropzone) dropzone.classList.toggle('has-image', !!tourSnapshot.dropHas && !!tourSnapshot.sourceSrc);
  if(finalImg){
    if(tourSnapshot.finalSrc) finalImg.src = tourSnapshot.finalSrc;
    else if(!(lastState && lastState.has_final)){
      finalImg.removeAttribute('src'); finalImg.src = '';
    }
  }
  if(chatInput) chatInput.value = tourSnapshot.chatVal || '';
  const canvas = document.getElementById('editMarkupCanvas');
  if(canvas){
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if(tourSnapshot.markupData){
      const img = new Image();
      img.onload = () => {
        try{ ctx.drawImage(img, 0, 0, canvas.width, canvas.height); }catch(_){}
      };
      img.src = tourSnapshot.markupData;
    }
  }
  editTool = tourSnapshot.editTool || null;
  markupUsedBrush = !!tourSnapshot.markupUsedBrush;
  markupUsedEraser = !!tourSnapshot.markupUsedEraser;
  updateEditToolUi();
  document.getElementById('busyOverlay')?.classList.remove('open', 'tour-demo');
  document.querySelectorAll('.tour-demo-flash,.tour-click-flash,.tour-playing').forEach(el => {
    el.classList.remove('tour-demo-flash', 'tour-click-flash', 'tour-playing');
  });
  const stage = document.getElementById('resultStage');
  if(stage && !(editTool && lastState.has_final)) stage.classList.remove('is-editing');
  setMarkupEnabled(!!lastState.has_final && !busy);
  moveTourCursorTo(null, false);
}
function clearTourAction(){
  clearTourTimers();
  closeTourBusyDemo();
  document.getElementById('busyOverlay')?.classList.remove('open', 'tour-demo');
  document.querySelectorAll('.tour-demo-flash,.tour-click-flash,.tour-playing').forEach(el => {
    el.classList.remove('tour-demo-flash', 'tour-click-flash', 'tour-playing');
  });
  // Reset demo tool state between tour steps; full restore happens on close.
  if(tourActive && tourSnapshot){
    editTool = tourSnapshot.editTool || null;
    markupUsedBrush = !!tourSnapshot.markupUsedBrush;
    markupUsedEraser = !!tourSnapshot.markupUsedEraser;
    updateEditToolUi();
  }
  const brushGroup = document.getElementById('quickBrushGroup');
  const eraserGroup = document.getElementById('quickEraserGroup');
  if(!editTool && !markupUsedBrush && !markupUsedEraser){
    if(brushGroup) brushGroup.classList.remove('open');
    if(eraserGroup) eraserGroup.classList.remove('open');
  }
  moveTourCursorTo(null, false);
}
function drawTourStroke(ctx, points, color, width){
  if(!ctx || !points.length) return;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = width || 14;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.globalCompositeOperation = 'source-over';
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for(let i=1;i<points.length;i++) ctx.lineTo(points[i].x, points[i].y);
  ctx.stroke();
}
function animateTourStroke(ctx, points, color, width, done){
  if(!ctx || !points.length){ if(done) done(); return; }
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = width || 14;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.globalCompositeOperation = 'source-over';
  ctx.beginPath();
  ctx.arc(points[0].x, points[0].y, (width || 14) / 2, 0, Math.PI * 2);
  ctx.fill();
  let i = 1;
  const step = () => {
    if(!tourActive) return;
    if(i >= points.length){ if(done) done(); return; }
    ctx.beginPath();
    ctx.moveTo(points[i - 1].x, points[i - 1].y);
    ctx.lineTo(points[i].x, points[i].y);
    ctx.stroke();
    i += 1;
    if(i < points.length) tourDelay(step, 45);
    else if(done) done();
  };
  if(points.length > 1) tourDelay(step, 45);
  else if(done) done();
}
function ensureTourFinalImage(done){
  const finalImg = document.getElementById('finalImg');
  if(!finalImg){ if(done) done(); return; }
  const src = finalImg.getAttribute('src') || '';
  if(src.includes('/assets/studio_tour/after.png') && finalImg.complete && finalImg.naturalWidth > 0){
    if(done) done();
    return;
  }
  let started = false;
  const finish = () => {
    if(started) return;
    started = true;
    if(done) done();
  };
  // Same broken src may not re-fire load/error — force a one-shot retry URL.
  const needsRetry = src.includes('/assets/studio_tour/after.png') && !(finalImg.naturalWidth > 0);
  finalImg.addEventListener('load', finish, {once:true});
  finalImg.addEventListener('error', finish, {once:true});
  finalImg.src = needsRetry ? (TOUR_AFTER + '?retry=' + Date.now()) : TOUR_AFTER;
  if(finalImg.complete && finalImg.naturalWidth > 0) tourDelay(finish, 20);
  tourDelay(finish, 1200); // never hang tour demos
}
function preloadTourAssets(){
  [TOUR_BEFORE, TOUR_AFTER].forEach(src => {
    const img = new Image();
    img.src = src;
  });
}
function openTourBusyDemo(){
  const overlay = document.getElementById('busyOverlay');
  const busyText = document.getElementById('busyText');
  const busyTitle = document.getElementById('busyTitle');
  if(busyTitle) busyTitle.textContent = 'Идёт генерация';
  if(busyText) busyText.textContent = 'Демо: агент собирает ночную концепцию…';
  overlay?.classList.add('open', 'tour-demo');
}
function closeTourBusyDemo(){
  const overlay = document.getElementById('busyOverlay');
  overlay?.classList.remove('open', 'tour-demo');
}
function buildStrokePath(w, h, kind){
  if(kind === 'brush'){
    const y = h * 0.30;
    return [
      {x:w*0.16,y:y},{x:w*0.22,y:y-2},{x:w*0.28,y:y},{x:w*0.34,y:y+2},
      {x:w*0.40,y:y},{x:w*0.46,y:y-1},{x:w*0.52,y:y}
    ];
  }
  const y = h * 0.55;
  return [
    {x:w*0.55,y:y},{x:w*0.62,y:y-1},{x:w*0.69,y:y},{x:w*0.76,y:y+1},{x:w*0.84,y:y}
  ];
}
function playMarkupDemo(attempt){
  if(!tourActive) return;
  const stage = document.getElementById('resultStage');
  const brushBtn = document.getElementById('editBrushBtn');
  const eraserBtn = document.getElementById('editEraserBtn');
  setMarkupEnabled(true);
  syncEditMarkupCanvas();
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return;
  const w = Math.max(1, canvas.width);
  const h = Math.max(1, canvas.height);
  if(w < 8 || h < 8){
    if((attempt || 0) < 8){
      tourDelay(() => playMarkupDemo((attempt || 0) + 1), 120);
    }
    return;
  }
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  editTool = 'brush';
  updateEditToolUi();
  const brushPath = buildStrokePath(w, h, 'brush');
  animateTourStroke(ctx, brushPath, 'rgba(255,70,70,0.92)', Math.max(10, w * 0.02), () => {
    if(!tourActive) return;
    markupUsedBrush = true;
    moveTourCursorTo(eraserBtn, true);
    eraserBtn?.classList.add('tour-click-flash');
    tourDelay(() => {
      if(!tourActive) return;
      editTool = 'eraser';
      updateEditToolUi();
      const eraserPath = buildStrokePath(w, h, 'eraser');
      animateTourStroke(ctx, eraserPath, 'rgba(79,209,197,0.92)', Math.max(10, w * 0.018), () => {
        if(!tourActive) return;
        markupUsedEraser = true;
        updateEditToolUi();
        moveTourCursorTo(stage, true);
      });
    }, 350);
  });
}
function runTourAction(action){
  clearTourAction();
  if(!action) return;
  // Prevent accidental real clicks under the spotlight while demos play.
  document.getElementById('startBtn')?.setAttribute('disabled', 'disabled');
  document.getElementById('chatBtn')?.setAttribute('disabled', 'disabled');
  const dropzone = document.getElementById('dropzone');
  const sourceImg = document.getElementById('sourceImg');
  const finalImg = document.getElementById('finalImg');
  const stage = document.getElementById('resultStage');
  const startBtn = document.getElementById('startBtn');
  const brushBtn = document.getElementById('editBrushBtn');
  const eraserBtn = document.getElementById('editEraserBtn');
  const chatInput = document.getElementById('chatInput');
  const chatBtn = document.getElementById('chatBtn');
  const downloadBtn = document.getElementById('downloadBtn');
  const copyBtn = document.getElementById('copyFinalBtn');
  const maxCard = document.getElementById('maxSupportCard');

  if(action === 'beforeAfter'){
    ensureTourFinalImage(() => {
      if(!tourActive) return;
      if(stage) stage.classList.add('tour-playing');
    });
  }
  if(action === 'upload'){
    if(dropzone) dropzone.classList.add('tour-demo-flash');
    moveTourCursorTo(dropzone, true);
    tourDelay(() => {
      if(!tourActive) return;
      if(sourceImg){ sourceImg.src = TOUR_BEFORE; }
      if(dropzone) dropzone.classList.add('has-image');
      moveTourCursorTo(dropzone, true);
    }, 500);
  }
  if(action === 'generate'){
    if(sourceImg && !(sourceImg.getAttribute('src'))){
      sourceImg.src = TOUR_BEFORE;
      dropzone?.classList.add('has-image');
    }
    moveTourCursorTo(startBtn, true);
    startBtn?.classList.add('tour-click-flash');
    tourDelay(() => {
      if(!tourActive) return;
      openTourBusyDemo();
    }, 450);
    tourDelay(() => {
      if(!tourActive) return;
      closeTourBusyDemo();
      ensureTourFinalImage(() => {
        if(!tourActive) return;
        stage?.classList.add('tour-playing');
        moveTourCursorTo(stage, true);
      });
    }, 1400);
  }
  if(action === 'result'){
    ensureTourFinalImage(() => {
      if(!tourActive) return;
      stage?.classList.add('tour-playing');
      moveTourCursorTo(downloadBtn, true);
      downloadBtn?.classList.add('tour-click-flash');
      tourDelay(() => {
        if(!tourActive) return;
        moveTourCursorTo(copyBtn, true);
        copyBtn?.classList.add('tour-click-flash');
      }, 900);
    });
  }
  if(action === 'markup'){
    stage?.classList.add('tour-playing');
    moveTourCursorTo(brushBtn, true);
    brushBtn?.classList.add('tour-click-flash');
    ensureTourFinalImage(() => {
      if(!tourActive) return;
      playMarkupDemo(0);
    });
  }
  if(action === 'chat'){
    const brushGroup = document.getElementById('quickBrushGroup');
    const eraserGroup = document.getElementById('quickEraserGroup');
    if(brushGroup) brushGroup.classList.add('open');
    if(eraserGroup) eraserGroup.classList.add('open');
    moveTourCursorTo(brushGroup || chatInput, true);
    const demoText = 'проставь прожектор в красной зоне и убери отмеченное голубым';
    if(chatInput){
      chatInput.value = '';
      let i = 0;
      const typeNext = () => {
        if(!tourActive || i > demoText.length) return;
        chatInput.value = demoText.slice(0, i);
        i += 1;
        tourDelay(typeNext, 28);
      };
      tourDelay(typeNext, 400);
    }
    tourDelay(() => {
      if(!tourActive) return;
      moveTourCursorTo(chatBtn, true);
      chatBtn?.classList.add('tour-click-flash');
    }, 2200);
  }
  if(action === 'max'){
    moveTourCursorTo(maxCard, true);
    maxCard?.classList.add('tour-click-flash');
  }
  if(action === 'done'){
    const help = document.getElementById('helpBtnPromo');
    moveTourCursorTo(help, true);
    help?.classList.add('tour-click-flash');
  }
}

function qs(){ return new URLSearchParams(location.search); }
function esc(s){ return String(s??'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function api(path, opts={}){
  const res = await fetch(path, opts);
  const data = await res.json().catch(()=>({}));
  if(!res.ok){
    let detail = data.detail || res.statusText || 'Ошибка';
    if(Array.isArray(detail)) detail = detail.map(x => x.msg || String(x)).join(', ');
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return data;
}
function setBusy(on, msg){
  busy = !!on;
  const box = document.getElementById('statusBox');
  box.classList.toggle('busy', busy);
  box.classList.remove('err');
  if(msg) box.textContent = msg;
  document.getElementById('startBtn').disabled = busy || !projectId;
  const regenBtn = document.getElementById('regenBtn');
  if(regenBtn) regenBtn.disabled = busy || !projectId;
  document.getElementById('chatBtn').disabled = busy || !projectId;
  document.getElementById('downloadBtn').disabled = !lastState.has_final;
  setMarkupEnabled(!!lastState.has_final && !busy);
  const overlay = document.getElementById('busyOverlay');
  const busyText = document.getElementById('busyText');
  const busyTitle = document.getElementById('busyTitle');
  if(overlay){
    if(busy) overlay.classList.remove('tour-demo');
    overlay.classList.toggle('open', busy);
    overlay.setAttribute('aria-busy', busy ? 'true' : 'false');
  }
  if(busy && busyText && msg) busyText.textContent = msg;
  if(busyTitle){
    busyTitle.textContent = busy
      ? ((msg && /загружаю картинк|загружаю результат/i.test(msg))
          ? 'Почти готово'
          : ((msg && /правк|разметк|редактир/i.test(msg)) ? 'Идёт правка' : 'Идёт генерация'))
      : 'Идёт генерация';
  }
}
function loadFinalImageAndWait(img, url, timeoutMs){
  return new Promise((resolve) => {
    if(!img || !url){ resolve(false); return; }
    let done = false;
    const finish = (ok) => {
      if(done) return;
      done = true;
      try{ img.removeEventListener('load', onLoad); }catch(_){}
      try{ img.removeEventListener('error', onErr); }catch(_){}
      if(timer) clearTimeout(timer);
      resolve(!!ok);
    };
    const onLoad = () => finish(img.naturalWidth > 0);
    const onErr = () => finish(false);
    const timer = setTimeout(() => finish(img.complete && img.naturalWidth > 0), timeoutMs || 60000);
    img.addEventListener('load', onLoad);
    img.addEventListener('error', onErr);
    img.src = url;
    // Cached images may already be complete right after assigning src.
    if(img.complete && img.naturalWidth > 0){
      requestAnimationFrame(() => finish(true));
    }
  });
}
function setError(msg){
  const box = document.getElementById('statusBox');
  box.classList.add('err');
  box.classList.remove('busy');
  box.textContent = msg;
  busy = false;
  const overlay = document.getElementById('busyOverlay');
  if(overlay){
    overlay.classList.remove('open');
    overlay.setAttribute('aria-busy', 'false');
  }
}
function renderChat(chat){
  const box = document.getElementById('chatBox');
  const items = chat || [];
  box.innerHTML = items.map(m => `<div class="bubble ${esc(m.role||'assistant')}">${esc(m.text||'')}</div>`).join('')
    || '<div class="muted">История чата появится после первой генерации</div>';
  box.scrollTop = box.scrollHeight;
}
async function applyStudioPayload(data){
  lastState = data || {};
  const st = data.state || {};
  renderChat(data.chat || []);
  // If a generation/edit is in flight, keep the overlay until the new photo is actually painted.
  const holdBusyForFinal = !!busy && !!data.final_url;

  const dropzone = document.getElementById('dropzone');
  const sourceImg = document.getElementById('sourceImg');
  if(data.source_url){
    sourceImg.src = data.source_url + '?t=' + Date.now();
    dropzone.classList.add('has-image');
  } else {
    sourceImg.removeAttribute('src');
    sourceImg.src = '';
    dropzone.classList.remove('has-image');
  }

  const finalImg = document.getElementById('finalImg');
  let finalReadyPromise = null;
  if(data.final_url){
    const nextSrc = data.final_url + '?t=' + Date.now();
    if(holdBusyForFinal){
      setBusy(true, 'Почти готово — загружаю картинку результата…');
      finalImg.onload = null;
      finalImg.onerror = null;
      finalReadyPromise = loadFinalImageAndWait(finalImg, nextSrc, 60000).then((ok) => {
        syncEditMarkupCanvas();
        return ok;
      });
    } else {
      finalImg.onload = () => { syncEditMarkupCanvas(); setMarkupEnabled(true); };
      finalImg.src = nextSrc;
    }
  } else {
    finalImg.onload = null;
    finalImg.removeAttribute('src');
    finalImg.src = '';
    clearEditMarkup();
    setMarkupEnabled(false);
  }

  const hist = document.getElementById('historyStrip');
  const activeId = data.active_history_id;
  const histStamp = Date.now();
  hist.innerHTML = (data.history || []).map(h => {
    const label = esc(h.kind || 'render') + (h.id != null ? (' #' + h.id) : '');
    const title = esc((h.note || h.prompt || h.feedback_comment || '').slice(0, 120));
    const active = h.active || String(h.id) === String(activeId);
    const vote = (h.feedback_vote || '').toLowerCase();
    let voteCls = 'pending';
    let voteText = '⏳ Нет оценки';
    if(vote === 'like'){ voteCls = 'like'; voteText = '👍 Нравится'; }
    else if(vote === 'dislike'){ voteCls = 'dislike'; voteText = '👎 Не нравится'; }
    else if((h.feedback_status || '').toLowerCase() === 'skipped'){ voteText = 'Пропущено'; }
    const comment = (h.feedback_comment || '').trim();
    const shortComment = comment ? (comment.length > 42 ? comment.slice(0, 42) + '…' : comment) : '';
    const annUrl = (h.annotation_url || '').trim();
    const hasAnn = !!annUrl;
    const url = String(h.url || '').trim();
    if(!url) return '';
    return `<button type="button" class="hist-item${active ? ' active' : ''}" title="${title}" data-hist-id="${esc(String(h.id))}" data-hist-url="${esc(url)}">
      <div class="hist-thumb">
        <img src="${esc(url)}?t=${histStamp}" alt="" loading="lazy" onerror="this.style.opacity='.35'">
        ${hasAnn ? `<img class="hist-ann" src="${esc(annUrl)}?t=${histStamp}" alt="разметка">` : ''}
      </div>
      <span>${label}${active ? ' · active' : ''}</span>
      ${hasAnn ? '<span class="hist-markup-tag">разметка · кисть/ластик</span>' : ''}
      <span class="hist-vote ${voteCls}">${esc(voteText)}</span>
      ${shortComment ? `<span class="hist-comment">${esc(shortComment)}</span>` : ''}
    </button>`;
  }).join('') || '<div class="muted">История версий появится после генерации</div>';
  hist.querySelectorAll('.hist-item[data-hist-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      restoreHistoryVersion(btn.getAttribute('data-hist-id'), btn.getAttribute('data-hist-url') || '');
    });
  });
  const hint = document.getElementById('activeHistoryHint');
  if(hint){
    hint.textContent = activeId != null
      ? ('Активна версия #' + activeId + ' — кисть/ластик и «Отправить» правят её')
      : ((data.history || []).length ? 'Выберите версию в истории, чтобы править именно её' : '');
  }
  document.getElementById('downloadBtn').disabled = !data.has_final;
  const copyBtn = document.getElementById('copyFinalBtn');
  if(copyBtn) copyBtn.disabled = !data.has_final;
  document.getElementById('chatBtn').disabled = !projectId || busy;
  const regenBtnApply = document.getElementById('regenBtn');
  if(regenBtnApply) regenBtnApply.disabled = !projectId || busy;
  setMarkupEnabled(!!data.has_final && !busy);
  updateEditToolUi();
  scheduleFeedbackPrompt(data);
  if(data.has_final){
    if(finalReadyPromise){
      try{ await finalReadyPromise; }catch(_){}
    }
    const usedModel = data.routerai_model || (data.state && data.state.routerai_model) || '';
    setBusy(false, usedModel
      ? ('Готово · модель: ' + usedModel + '. Смотрите результат в центре.')
      : 'Готово. Смотрите результат в центре — кисть/ластик для правок.');
    // Keep the result in view — never jump to the feedback block after generation.
    try{
      requestAnimationFrame(() => {
        document.getElementById('resultCard')?.scrollIntoView({behavior:'smooth', block:'center'});
      });
    }catch(_){}
  }
}
function clearTourTarget(){
  document.querySelectorAll('.tour-target-live').forEach(el => el.classList.remove('tour-target-live', 'tour-pulse'));
}
function positionCoachCard(targetRect, place){
  const card = document.getElementById('coachCard');
  if(!card) return;
  const pad = 12;
  const cw = card.offsetWidth || 360;
  const ch = card.offsetHeight || 200;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let top, left;
  const prefer = place || 'below';
  if(prefer === 'above'){
    top = targetRect.top - ch - 14;
    if(top < pad) top = targetRect.bottom + 14;
  } else {
    top = targetRect.bottom + 14;
    if(top + ch > vh - pad) top = Math.max(pad, targetRect.top - ch - 14);
  }
  left = targetRect.left + (targetRect.width / 2) - (cw / 2);
  left = Math.max(pad, Math.min(left, vw - cw - pad));
  top = Math.max(pad, Math.min(top, vh - ch - pad));
  card.style.top = Math.round(top) + 'px';
  card.style.left = Math.round(left) + 'px';
}
function positionTourChrome(target, step){
  const hole = document.getElementById('coachHole');
  const shade = document.getElementById('coachShade');
  if(!target){
    if(shade) shade.style.display = 'block';
    if(hole) hole.style.display = 'none';
    const card = document.getElementById('coachCard');
    if(card){
      card.style.top = '20%';
      card.style.left = '50%';
      card.style.transform = 'translateX(-50%)';
    }
    return;
  }
  const rect = target.getBoundingClientRect();
  const pad = 8;
  if(shade) shade.style.display = 'none';
  if(hole){
    hole.style.display = 'block';
    hole.style.top = Math.max(0, rect.top - pad) + 'px';
    hole.style.left = Math.max(0, rect.left - pad) + 'px';
    hole.style.width = Math.max(24, rect.width + pad * 2) + 'px';
    hole.style.height = Math.max(24, rect.height + pad * 2) + 'px';
  }
  const card = document.getElementById('coachCard');
  if(card) card.style.transform = '';
  positionCoachCard({
    top: rect.top - pad,
    left: rect.left - pad,
    width: rect.width + pad * 2,
    height: rect.height + pad * 2,
    bottom: rect.bottom + pad,
    right: rect.right + pad
  }, step.place);
}
function renderStudioTour(opts){
  const onlyLayout = !!(opts && opts.onlyLayout);
  const step = STUDIO_TOUR[tourStep] || STUDIO_TOUR[0];
  if(!onlyLayout){
    clearTourTarget();
    document.getElementById('coachStepN').textContent = 'Шаг ' + (tourStep + 1) + ' из ' + STUDIO_TOUR.length;
    document.getElementById('coachTitle').textContent = step.title;
    document.getElementById('coachBody').innerHTML = step.html;
    document.getElementById('coachPrevBtn').style.visibility = tourStep > 0 ? 'visible' : 'hidden';
    document.getElementById('coachNextBtn').textContent = tourStep >= STUDIO_TOUR.length - 1 ? 'Понятно ✓' : 'Далее →';
  }

  const target = document.getElementById(step.target);
  if(!target){
    positionTourChrome(null, step);
    return;
  }
  if(!onlyLayout){
    target.classList.add('tour-target-live', 'tour-pulse');
    try{ target.scrollIntoView({behavior:'smooth', block:'nearest', inline:'nearest'}); }catch(_){}
  } else if(!target.classList.contains('tour-target-live')){
    target.classList.add('tour-target-live', 'tour-pulse');
  }
  clearTimeout(tourLayoutTimer);
  tourLayoutTimer = setTimeout(() => {
    if(!tourActive) return;
    positionTourChrome(target, step);
    if(!onlyLayout){
      const key = tourStep + ':' + (step.action || '');
      if(tourActionKey !== key){
        tourActionKey = key;
        runTourAction(step.action);
      }
    }
  }, onlyLayout ? 40 : 160);
}
function openStudioTour(){
  tourStep = 0;
  tourActive = true;
  tourActionKey = '';
  tourSnapshot = snapshotTourUi();
  preloadTourAssets();
  document.getElementById('coachRoot').classList.add('open');
  document.getElementById('studioTour').classList.remove('open');
  renderStudioTour();
  if(!tourResizeBound){
    tourResizeBound = true;
    window.addEventListener('resize', () => {
      if(!tourActive) return;
      clearTimeout(tourLayoutTimer);
      tourLayoutTimer = setTimeout(() => renderStudioTour({onlyLayout:true}), 60);
    });
    window.addEventListener('scroll', () => {
      if(!tourActive) return;
      clearTimeout(tourLayoutTimer);
      tourLayoutTimer = setTimeout(() => renderStudioTour({onlyLayout:true}), 60);
    }, true);
  }
}
function closeStudioTour(){
  tourActive = false;
  tourActionKey = '';
  clearTimeout(tourLayoutTimer);
  clearTourAction();
  restoreTourUi();
  tourSnapshot = null;
  document.getElementById('coachRoot').classList.remove('open');
  document.getElementById('studioTour').classList.remove('open');
  clearTourTarget();
  // Re-enable controls according to real project state
  document.getElementById('startBtn').disabled = busy || !projectId;
  document.getElementById('chatBtn').disabled = busy || !projectId;
  try{ localStorage.setItem('niteos_studio_tour_seen', '1'); }catch(_){}
}
function prevStudioTour(){
  if(tourStep > 0){
    clearTourAction();
    tourActionKey = '';
    tourStep--;
    renderStudioTour();
  }
}
function nextStudioTour(){
  if(tourStep >= STUDIO_TOUR.length - 1){ closeStudioTour(); return; }
  clearTourAction();
  tourActionKey = '';
  tourStep++;
  renderStudioTour();
}
function copyContactPhone(ev){
  if(ev){ try{ ev.preventDefault(); }catch(_){ } }
  const el = document.getElementById('contactPhoneLink');
  const phone = (el && (el.getAttribute('data-phone') || el.textContent) || '8 843 202 21 39').trim();
  const hint = document.getElementById('phoneCopyHint');
  const done = () => {
    if(hint){
      hint.style.display = 'inline';
      setTimeout(() => { hint.style.display = 'none'; }, 1600);
    }
    const box = document.getElementById('statusBox');
    if(box){
      box.classList.remove('busy', 'err');
      box.textContent = 'Номер скопирован: ' + phone;
    }
  };
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(phone).then(done).catch(() => {
      try{
        const ta = document.createElement('textarea');
        ta.value = phone; document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); ta.remove(); done();
      }catch(_){}
    });
  } else {
    try{
      const ta = document.createElement('textarea');
      ta.value = phone; document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); ta.remove(); done();
    }catch(_){}
  }
  return false;
}
function setFeedbackVote(vote){
  feedbackVote = (vote === 'like' || vote === 'dislike') ? vote : '';
  document.getElementById('feedbackLikeBtn')?.classList.toggle('active', feedbackVote === 'like');
  document.getElementById('feedbackDislikeBtn')?.classList.toggle('active', feedbackVote === 'dislike');
}
function openFeedbackGate(opts){
  const gate = document.getElementById('feedbackGate');
  if(!gate) return;
  const pendingNote = document.getElementById('feedbackGatePending');
  const statusEl = document.getElementById('feedbackGateStatus');
  const lead = document.getElementById('feedbackGateLead');
  const hasPending = !!(pendingAfterFeedback && pendingAfterFeedback.type);
  if(pendingNote){
    pendingNote.classList.toggle('hidden', !hasPending);
    const labels = {generate:'генерацию', chat:'правку', createProject:'создание нового проекта'};
    const what = labels[pendingAfterFeedback?.type] || 'действие';
    pendingNote.textContent = hasPending
      ? ('После оценки сразу продолжим: ' + what + '.')
      : '';
  }
  if(lead){
    lead.textContent = (opts && opts.message)
      ? String(opts.message)
      : 'Без оценки нельзя продолжить: ни генерацию, ни правку, ни новый проект.';
  }
  if(statusEl){
    statusEl.classList.remove('err');
    statusEl.textContent = '';
  }
  gate.classList.add('open');
  try{ document.getElementById('feedbackGateLikeBtn')?.focus({preventScroll:true}); }catch(_){}
}
function closeFeedbackGate(){
  const gate = document.getElementById('feedbackGate');
  if(gate) gate.classList.remove('open');
  const statusEl = document.getElementById('feedbackGateStatus');
  if(statusEl){
    statusEl.classList.remove('err');
    statusEl.textContent = '';
  }
  setFeedbackGateBusy(false);
}
function cancelFeedbackGate(){
  // Close modal only — pending action is dropped so user stays where they were.
  pendingAfterFeedback = null;
  closeFeedbackGate();
  const box = document.getElementById('statusBox');
  if(box){
    box.classList.remove('busy');
    box.classList.add('err');
    box.textContent = 'Нужна оценка результата. Нажмите действие снова — снова откроется окно оценки.';
  }
}
function setFeedbackGateBusy(on){
  const like = document.getElementById('feedbackGateLikeBtn');
  const dislike = document.getElementById('feedbackGateDislikeBtn');
  const cancel = document.getElementById('feedbackGateCancelBtn');
  if(like) like.disabled = !!on;
  if(dislike) dislike.disabled = !!on;
  if(cancel) cancel.disabled = !!on;
}
function openFeedbackZone(opts){
  const zone = document.getElementById('feedbackZone');
  if(!zone) return;
  zone.classList.add('open');
  const force = !!(opts && opts.forceFocus);
  if(force){
    // Required path always uses the blocking center modal — not a page scroll.
    openFeedbackGate({message: opts && opts.message});
    return;
  }
}
function hideFeedbackToast(){
  const toast = document.getElementById('feedbackToast');
  if(toast) toast.classList.add('hidden');
}
function promptFeedbackRequired(message, pending){
  if(pending) pendingAfterFeedback = pending;
  setError(message || 'Сначала оцените предыдущий результат.');
  openFeedbackGate({
    message: 'Поставьте оценку предыдущему результату — без этого дальше нельзя.'
  });
  const statusEl = document.getElementById('feedbackStatus');
  if(statusEl){
    statusEl.textContent = pending
      ? 'Поставьте оценку в окне — после этого продолжим автоматически.'
      : 'Оцените результат в окне, затем повторите действие.';
  }
  const gateStatus = document.getElementById('feedbackGateStatus');
  if(gateStatus){
    gateStatus.classList.remove('err');
    gateStatus.textContent = pending
      ? 'Выберите «Нравится» или «Не нравится» — и сразу продолжим.'
      : 'Выберите «Нравится» или «Не нравится».';
  }
}
function showFeedbackToast(){
  // Soft toast disabled — users need a blocking modal, not a corner hint.
  hideFeedbackToast();
}
function dismissFeedbackToast(){
  hideFeedbackToast();
  if(feedbackPromptedHistoryId) feedbackToastDismissedFor = feedbackPromptedHistoryId;
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
}
async function quickFeedbackFromToast(vote){
  await submitFeedbackFromGate(vote);
}
async function submitFeedbackFromGate(vote){
  setFeedbackVote(vote);
  const gateStatus = document.getElementById('feedbackGateStatus');
  if(gateStatus){
    gateStatus.classList.remove('err');
    gateStatus.textContent = 'Сохраняем оценку…';
  }
  setFeedbackGateBusy(true);
  try{
    await submitFeedback({fromGate:true});
  }finally{
    setFeedbackGateBusy(false);
  }
}
function latestHistoryNeedsFeedback(state){
  if(!state) return false;
  const hist = Array.isArray(state.history) ? state.history : [];
  const last = hist.length ? hist[hist.length - 1] : (state.last_history_entry || null);
  if(!last) return !!state.feedback_required;
  const vote = String(last.feedback_vote || '').trim().toLowerCase();
  if(vote === 'like' || vote === 'dislike') return false;
  // skipped / empty / missing vote → still must rate before next gen/edit
  return true;
}
function scheduleFeedbackPrompt(state){
  const zone = document.getElementById('feedbackZone');
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  hideFeedbackToast();
  // Keep optional side form closed after render/refresh.
  // Do NOT auto-open the blocking gate here — only when user tries next action.
  if(zone) zone.classList.remove('open', 'required', 'blocking');
  if(!pendingAfterFeedback) closeFeedbackGate();
  if(!state || !state.has_final){
    feedbackPromptedHistoryId = '';
    feedbackToastDismissedFor = '';
    return;
  }
  const needs = latestHistoryNeedsFeedback(state);
  state.feedback_required = needs;
  if(!needs){
    closeFeedbackGate();
    return;
  }
  const hist = Array.isArray(state.history) ? state.history : [];
  const history = hist.length ? hist[hist.length - 1] : (state.last_history_entry || {});
  const renderId = String(history.id || 'current');
  if(feedbackPromptedHistoryId !== renderId){
    feedbackVote = '';
    setFeedbackVote('');
    feedbackToastDismissedFor = '';
    const issue = document.getElementById('feedbackIssue');
    const comment = document.getElementById('feedbackComment');
    const gateComment = document.getElementById('feedbackGateComment');
    const contact = document.getElementById('feedbackContact');
    const status = document.getElementById('feedbackStatus');
    if(issue) issue.value = '';
    if(comment) comment.value = '';
    if(gateComment) gateComment.value = '';
    if(contact) contact.value = '';
    if(status) status.textContent = 'Оценка нужна перед следующей генерацией, правкой или новым проектом.';
    feedbackPromptedHistoryId = renderId;
  }
}
function requireFeedbackBeforeAction(pending){
  // Правки по разметке/чату не блокируем оценкой — иначе нельзя итеративно править.
  // Оценка обязательна перед новой генерацией или новым проектом.
  const kind = (pending && pending.type) || '';
  if(kind === 'chat') return false;
  if(latestHistoryNeedsFeedback(lastState)){
    if(lastState) lastState.feedback_required = true;
    promptFeedbackRequired(
      'Сначала оцените предыдущий результат (Нравится / Не нравится) — после оценки продолжим.',
      pending || null
    );
    return true;
  }
  return false;
}
async function resumePendingAfterFeedback(){
  const pending = pendingAfterFeedback;
  pendingAfterFeedback = null;
  if(!pending || !pending.type) return;
  const statusEl = document.getElementById('feedbackStatus');
  if(statusEl) statusEl.textContent = 'Оценка принята — продолжаем…';
  const gateStatus = document.getElementById('feedbackGateStatus');
  if(gateStatus) gateStatus.textContent = 'Оценка принята — продолжаем…';
  if(pending.type === 'generate'){
    await runStudioGeneration({skipFeedbackGate:true});
    return;
  }
  if(pending.type === 'chat'){
    await sendChat({skipFeedbackGate:true});
    return;
  }
  if(pending.type === 'createProject'){
    await createProject({skipFeedbackGate:true});
  }
}
async function submitFeedback(opts){
  const statusEl = document.getElementById('feedbackStatus');
  const gateStatus = document.getElementById('feedbackGateStatus');
  const btn = document.getElementById('feedbackSubmitBtn');
  const fromGate = !!(opts && opts.fromGate);
  if(statusEl) statusEl.textContent = '';
  if(!feedbackVote){
    if(statusEl) statusEl.textContent = 'Выберите: нравится или не нравится.';
    openFeedbackGate({message:'Сначала выберите: Нравится или Не нравится.'});
    return;
  }
  if(!projectId) return;
  try{
    if(btn) btn.disabled = true;
    setFeedbackGateBusy(true);
    const fd = new FormData();
    fd.append('vote', feedbackVote);
    fd.append('issue_type', document.getElementById('feedbackIssue')?.value || '');
    const gateComment = (document.getElementById('feedbackGateComment')?.value || '').trim();
    const sideComment = (document.getElementById('feedbackComment')?.value || '').trim();
    const comment = fromGate ? (gateComment || sideComment) : (sideComment || gateComment);
    fd.append('comment', comment);
    fd.append('contact', document.getElementById('feedbackContact')?.value || '');
    await api(`/api/projects/${projectId}/feedback`, {method:'POST', body: fd});
    const gateCommentEl = document.getElementById('feedbackGateComment');
    if(gateCommentEl) gateCommentEl.value = '';
    if(document.getElementById('feedbackComment') && fromGate && gateComment){
      document.getElementById('feedbackComment').value = gateComment;
    }
    if(statusEl) statusEl.textContent = 'Спасибо! Оценка сохранена к этой версии в истории.';
    if(gateStatus){
      gateStatus.classList.remove('err');
      gateStatus.textContent = 'Спасибо! Продолжаем…';
    }
    lastState.feedback_required = false;
    if(Array.isArray(lastState.history) && lastState.history.length){
      const last = lastState.history[lastState.history.length - 1];
      if(last) last.feedback_vote = feedbackVote;
    }
    const zone = document.getElementById('feedbackZone');
    if(zone) zone.classList.remove('required', 'blocking');
    hideFeedbackToast();
    dismissFeedbackToast();
    closeFeedbackGate();
    try{ await refreshState(); }catch(_){}
    await resumePendingAfterFeedback();
  }catch(err){
    const msg = String(err.message || err);
    if(statusEl) statusEl.textContent = msg;
    if(gateStatus){
      gateStatus.classList.add('err');
      gateStatus.textContent = msg;
    }
    if(fromGate) openFeedbackGate({});
  }finally{
    if(btn) btn.disabled = false;
    setFeedbackGateBusy(false);
  }
}
function maybeShowWelcomeTour(){
  try{
    if(localStorage.getItem('niteos_studio_tour_seen') === '1') return;
  }catch(_){}
  setTimeout(() => openStudioTour(), 500);
}
function previewHistory(url){
  const img = document.getElementById('finalImg');
  if(!img || !url) return;
  const next = url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
  img.onload = () => syncEditMarkupCanvas();
  img.onerror = () => setError('Не удалось загрузить версию из истории');
  img.src = next;
  clearEditMarkup();
}
async function restoreHistoryVersion(historyId, previewUrl){
  if(!projectId || historyId == null || historyId === '') return;
  if(busy){
    setError('Дождитесь окончания текущей операции, затем переключите версию');
    return;
  }
  // Instant preview so the main result never goes blank while the API runs.
  if(previewUrl) previewHistory(previewUrl);
  try{
    setBusy(true, 'Восстанавливаю версию #' + historyId + ' как активную…');
    const fd = new FormData();
    fd.append('history_id', String(historyId));
    const data = await api(`/api/projects/${projectId}/studio/restore-history`, {method:'POST', body: fd});
    clearEditMarkup();
    await refreshState();
    setBusy(false, data.message || ('Версия #' + historyId + ' активна. Рисуйте и жмите «Отправить».'));
    try{
      document.getElementById('resultCard')?.scrollIntoView({behavior:'smooth', block:'center'});
    }catch(_){}
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
function setMarkupEnabled(on){
  editMarkupReady = !!on;
  const canvas = document.getElementById('editMarkupCanvas');
  const stage = document.getElementById('resultStage');
  if(canvas){
    canvas.classList.toggle('hidden', !on);
    canvas.setAttribute('aria-hidden', on ? 'false' : 'true');
  }
  if(stage) stage.classList.toggle('is-editing', !!on);
  if(on) syncEditMarkupCanvas();
  updateEditToolUi();
}
function updateEditToolUi(){
  const brush = document.getElementById('editBrushBtn');
  const eraser = document.getElementById('editEraserBtn');
  const canvas = document.getElementById('editMarkupCanvas');
  const hint = document.getElementById('markupHint');
  const input = document.getElementById('chatInput');
  const toolOn = !!editTool && editMarkupReady;
  if(brush) brush.classList.toggle('active', editTool === 'brush');
  if(eraser) eraser.classList.toggle('active', editTool === 'eraser');
  if(canvas){
    canvas.classList.toggle('tool-on', toolOn);
    canvas.style.cursor = editTool === 'eraser' ? 'cell' : (editTool === 'brush' ? 'crosshair' : 'default');
  }
  syncQuickPromptsForTool();
  if(hint){
    if(editTool === 'eraser' || editTool === 'brush' || markupUsedBrush || markupUsedEraser){
      hint.style.display = 'block';
      hint.classList.add('busy');
      const parts = [];
      if(editTool === 'brush') parts.push('Шаг 1: рисуйте красным на фото');
      if(editTool === 'eraser') parts.push('Шаг 1: рисуйте голубым на фото');
      if(markupHasPaint()) parts.push('зона есть — дальше шаг 2 в чате справа');
      else parts.push('сначала отметьте зону на фото');
      hint.textContent = parts.join(' · ') + '.';
    } else {
      hint.style.display = 'none';
      hint.classList.remove('busy');
    }
  }
  if(input){
    if(markupHasPaint()){
      input.placeholder = markupUsedEraser && !markupUsedBrush
        ? 'Шаг 2: выберите шаблон «Убери…» или напишите, что убрать в голубой зоне…'
        : (markupUsedBrush && !markupUsedEraser
          ? 'Шаг 2: выберите шаблон «Измени…/Проставь…» или напишите, что сделать в красной зоне…'
          : 'Шаг 2: выберите шаблон(ы) или опишите правку по отмеченным зонам…');
    } else if(editTool === 'eraser'){
      input.placeholder = 'Сначала отметьте зону голубым на фото…';
    } else if(editTool === 'brush'){
      input.placeholder = 'Сначала отметьте зону красным на фото…';
    } else {
      input.placeholder = 'Можно просто написать: убери левый / сделай теплее / проставь прожектор у входа…';
    }
  }
  updateMarkupNextStep();
}
function updateMarkupNextStep(){
  const box = document.getElementById('markupNextStep');
  const panel = document.getElementById('chatStepPanel');
  const chatCard = document.getElementById('chatCard');
  const chatWrap = document.getElementById('chatSendTour');
  const idleNote = document.getElementById('chatIdleNote');
  const quick = document.getElementById('quickPrompts');
  const title = document.getElementById('chatStepTitle');
  const hasPaint = !tourActive && markupHasPaint();
  const needsText = hasPaint && !(document.getElementById('chatInput')?.value || '').trim();
  if(box) box.classList.toggle('open', hasPaint);
  if(panel) panel.classList.toggle('open', hasPaint);
  if(chatCard) chatCard.classList.toggle('awaiting-instruction', needsText);
  if(chatWrap) chatWrap.classList.toggle('needs-instruction', needsText);
  if(idleNote) idleNote.style.display = hasPaint ? 'none' : '';
  if(quick) quick.classList.toggle('awaiting', hasPaint);
  if(title){
    if(markupUsedBrush && markupUsedEraser){
      title.textContent = 'Красная и голубая зоны отмечены — что сделать?';
    } else if(markupUsedEraser && !markupUsedBrush){
      title.textContent = 'Голубая зона отмечена — что убрать?';
    } else if(markupUsedBrush){
      title.textContent = 'Красная зона отмечена — что изменить?';
    } else {
      title.textContent = 'Зона отмечена — что сделать?';
    }
  }
}
function revealChatStepPanel(focusInput){
  syncQuickPromptsForTool();
  updateMarkupNextStep();
  const card = document.getElementById('chatCard');
  try{ card?.scrollIntoView({behavior:'smooth', block:'start'}); }catch(_){}
  if(focusInput) focusChatInstruction();
  else {
    const root = document.getElementById('quickPrompts');
    try{ root?.scrollIntoView({behavior:'smooth', block:'nearest'}); }catch(_){}
  }
}
function focusChatInstruction(){
  const input = document.getElementById('chatInput');
  const wrap = document.getElementById('chatSendTour');
  syncQuickPromptsForTool();
  updateMarkupNextStep();
  try{ document.getElementById('chatCard')?.scrollIntoView({behavior:'smooth', block:'start'}); }catch(_){}
  if(wrap) wrap.classList.add('needs-instruction');
  if(input){
    try{ input.focus({preventScroll:true}); }catch(_){ try{ input.focus(); }catch(__){} }
  }
  const box = document.getElementById('statusBox');
  if(box){
    box.classList.remove('busy', 'err');
    box.textContent = 'В чате справа: напишите правку или нажмите шаблон, затем «Отправить».';
  }
}
function scrollToQuickTemplates(){
  syncQuickPromptsForTool();
  updateMarkupNextStep();
  const root = document.getElementById('quickPrompts');
  try{ document.getElementById('chatCard')?.scrollIntoView({behavior:'smooth', block:'start'}); }catch(_){}
  try{ root?.scrollIntoView({behavior:'smooth', block:'nearest'}); }catch(_){}
  if(root){
    root.classList.add('awaiting');
    root.style.outline = '2px solid #4fd1c5';
    setTimeout(() => { try{ root.style.outline = ''; }catch(_){} }, 1600);
  }
  const box = document.getElementById('statusBox');
  if(box){
    box.classList.remove('busy', 'err');
    box.textContent = markupUsedEraser && !markupUsedBrush
      ? 'В чате: нажмите голубой шаблон «Убери…», затем «Отправить».'
      : (markupUsedBrush && !markupUsedEraser
        ? 'В чате: нажмите красный шаблон, затем «Отправить».'
        : 'В чате: выберите шаблон(ы), затем «Отправить».');
  }
}
function promptMarkupInstructionNeeded(){
  updateMarkupNextStep();
  setError('Зона отмечена. В чате справа выберите шаблон или напишите, что сделать — затем «Отправить».');
  revealChatStepPanel(false);
  highlightChatInstruction();
}
function highlightChatInstruction(){
  const wrap = document.getElementById('chatSendTour');
  const input = document.getElementById('chatInput');
  const card = document.getElementById('chatCard');
  if(card) card.classList.add('awaiting-instruction');
  if(wrap){
    wrap.classList.add('needs-instruction');
    setTimeout(() => {
      if(input && !(input.value || '').trim() && markupHasPaint()) wrap.classList.add('needs-instruction');
    }, 0);
  }
  try{ input?.focus({preventScroll:true}); }catch(_){ try{ input?.focus(); }catch(__){} }
}
function syncQuickPromptsForTool(){
  const brushGroup = document.getElementById('quickBrushGroup');
  const eraserGroup = document.getElementById('quickEraserGroup');
  const root = document.getElementById('quickPrompts');
  // Show chat quick buttons only after the user has actually drawn —
  // turning on brush/eraser alone must keep attention on the photo.
  // During the interactive tour, keep chat panels closed so demos stay on the result.
  const showPanels = !tourActive && (markupUsedBrush || markupUsedEraser);
  if(brushGroup) brushGroup.classList.toggle('open', showPanels && markupUsedBrush);
  if(eraserGroup) eraserGroup.classList.toggle('open', showPanels && markupUsedEraser);
  if(!root) return;
  root.querySelectorAll('button[data-tool="any"]').forEach(btn => {
    btn.classList.remove('dim');
  });
  // Do not scroll to chat on tool toggle — user must stay on the image to draw.
}
function toggleEditTool(tool){
  const next = (tool === 'eraser') ? 'eraser' : 'brush';
  const turningOn = editTool !== next;
  editTool = turningOn ? next : null;
  updateEditToolUi();
  if(turningOn){
    if(lastState.has_final) setMarkupEnabled(true);
    const stage = document.getElementById('resultStage');
    const canvas = document.getElementById('editMarkupCanvas');
    try{ stage?.scrollIntoView({behavior:'smooth', block:'nearest'}); }catch(_){}
    try{ canvas?.focus({preventScroll:true}); }catch(_){ try{ canvas?.focus(); }catch(__){} }
    const box = document.getElementById('statusBox');
    if(box){
      box.classList.remove('busy', 'err');
      box.textContent = editTool === 'eraser'
        ? 'Ластик включён: рисуйте голубым на фото, затем опишите правку в чате'
        : 'Кисть включена: рисуйте красным на фото, затем опишите правку в чате';
    }
  }
}
function setEditTool(tool){
  // legacy alias
  toggleEditTool(tool);
}
function updateEditBrushSize(v){
  editBrushSize = Math.max(4, Math.min(48, Number(v) || 16));
}
function getFinalImageLayout(){
  const stage = document.getElementById('resultStage');
  const img = document.getElementById('finalImg');
  if(!stage || !img || !img.naturalWidth || !img.naturalHeight) return null;
  const sw = stage.clientWidth || 1;
  const sh = stage.clientHeight || 1;
  const nw = img.naturalWidth;
  const nh = img.naturalHeight;
  const scale = Math.min(sw / nw, sh / nh);
  const dw = nw * scale;
  const dh = nh * scale;
  const ox = (sw - dw) / 2;
  const oy = (sh - dh) / 2;
  return {sw, sh, nw, nh, dw, dh, ox, oy, scale};
}
function syncEditMarkupCanvas(){
  const canvas = document.getElementById('editMarkupCanvas');
  const layout = getFinalImageLayout();
  if(!canvas || !layout) return;
  canvas.style.left = layout.ox + 'px';
  canvas.style.top = layout.oy + 'px';
  canvas.style.width = layout.dw + 'px';
  canvas.style.height = layout.dh + 'px';
  const w = Math.max(1, Math.round(layout.dw));
  const h = Math.max(1, Math.round(layout.dh));
  if(canvas.width !== w || canvas.height !== h){
    const prev = document.createElement('canvas');
    prev.width = canvas.width; prev.height = canvas.height;
    if(canvas.width && canvas.height){
      prev.getContext('2d').drawImage(canvas, 0, 0);
    }
    canvas.width = w; canvas.height = h;
    if(prev.width && prev.height){
      canvas.getContext('2d').drawImage(prev, 0, 0, w, h);
    }
  }
}
function canvasPoint(e){
  const canvas = document.getElementById('editMarkupCanvas');
  const rect = canvas.getBoundingClientRect();
  const x = (e.clientX - rect.left) * (canvas.width / Math.max(1, rect.width));
  const y = (e.clientY - rect.top) * (canvas.height / Math.max(1, rect.height));
  return {x, y};
}
function editDrawPoint(e, isStart){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !editMarkupReady || !editTool) return;
  const ctx = canvas.getContext('2d');
  const p = canvasPoint(e);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = editBrushSize;
  if(editTool === 'eraser'){
    // Cyan = REMOVE luminaires (not destination-out wipe)
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = 'rgba(79,209,197,0.85)';
    ctx.fillStyle = 'rgba(79,209,197,0.85)';
    if(!markupUsedEraser){ markupUsedEraser = true; updateEditToolUi(); }
  } else {
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = 'rgba(255,70,70,0.88)';
    ctx.fillStyle = 'rgba(255,70,70,0.88)';
    if(!markupUsedBrush){ markupUsedBrush = true; updateEditToolUi(); }
  }
  if(isStart || !editLastPoint){
    ctx.beginPath();
    ctx.arc(p.x, p.y, editBrushSize / 2, 0, Math.PI * 2);
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.moveTo(editLastPoint.x, editLastPoint.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  }
  editLastPoint = p;
}
function bindMarkupCanvas(){
  if(markupBound) return;
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return;
  markupBound = true;
  canvas.addEventListener('pointerdown', (e)=>{
    if(!editMarkupReady || !editTool || busy) return;
    editDrawing = true;
    editDrawPoint(e, true);
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', (e)=>{
    if(!editMarkupReady || !editTool || !editDrawing) return;
    editDrawPoint(e, false);
  });
  canvas.addEventListener('pointerup', ()=>{
    editDrawing=false; editLastPoint=null;
    if(markupHasPaint()){
      updateEditToolUi();
      openZoneIntentPanel();
      const box = document.getElementById('statusBox');
      if(box && !busy){
        box.classList.remove('busy', 'err');
        box.textContent = 'Зона отмечена → в окне: что сделать с этим местом, затем «Отправить правку».';
      }
    }
  });
  canvas.addEventListener('pointerleave', ()=>{ editDrawing=false; editLastPoint=null; });
  window.addEventListener('resize', ()=>{ if(editMarkupReady) syncEditMarkupCanvas(); });
}
function openZoneIntentPanel(){
  const overlay = document.getElementById('zoneIntentOverlay');
  const title = document.getElementById('zoneIntentTitle');
  const lead = document.getElementById('zoneIntentLead');
  const input = document.getElementById('zoneIntentInput');
  if(!overlay) return;
  if(title){
    if(markupUsedBrush && markupUsedEraser){
      title.textContent = 'Красная и голубая зоны — что сделать?';
    } else if(markupUsedEraser && !markupUsedBrush){
      title.textContent = 'Голубая зона — что убрать?';
    } else if(markupUsedBrush){
      title.textContent = 'Красная зона — что сделать здесь?';
    } else {
      title.textContent = 'Что сделать с этой зоной?';
    }
  }
  if(lead){
    lead.textContent = markupUsedEraser && !markupUsedBrush
      ? 'Отмечено место для удаления света. Выберите «Убрать» или опишите своими словами.'
      : 'Отмечено место на фасаде. Можно поставить прожектор/линейный, изменить или убрать — остальное не тронем.';
  }
  // Prefer brush presets when both used; hide irrelevant chips lightly via opacity.
  document.querySelectorAll('#zoneIntentPresets [data-intent]').forEach((btn)=>{
    const intent = btn.getAttribute('data-intent') || '';
    let show = true;
    if(markupUsedEraser && !markupUsedBrush){
      show = intent === 'remove' || intent === 'change';
    } else if(markupUsedBrush && !markupUsedEraser){
      show = intent !== 'remove';
    }
    btn.style.display = show ? '' : 'none';
  });
  overlay.classList.add('open');
  try{ input?.focus({preventScroll:true}); }catch(_){ try{ input?.focus(); }catch(__){} }
  updateMarkupNextStep();
}
function closeZoneIntentPanel(clearInput){
  const overlay = document.getElementById('zoneIntentOverlay');
  const input = document.getElementById('zoneIntentInput');
  if(overlay) overlay.classList.remove('open');
  if(clearInput && input) input.value = '';
}
function pickZoneIntent(text){
  const input = document.getElementById('zoneIntentInput');
  if(!input) return;
  const next = String(text || '').trim();
  if(!next) return;
  const cur = (input.value || '').trim();
  input.value = cur ? (cur.replace(/\s+$/,'') + '\n' + next) : next;
  try{ input.focus({preventScroll:true}); }catch(_){}
}
async function submitZoneIntent(){
  const zoneInput = document.getElementById('zoneIntentInput');
  const chatInput = document.getElementById('chatInput');
  const text = (zoneInput && zoneInput.value || '').trim();
  if(!text){
    setError('Напишите или выберите, что сделать с зоной');
    try{ zoneInput?.focus(); }catch(_){}
    return;
  }
  if(!markupHasPaint()){
    setError('Сначала отметьте зону на фото');
    return;
  }
  if(chatInput) chatInput.value = text;
  closeZoneIntentPanel(false);
  await sendChat({skipFeedbackGate:true});
  if(zoneInput) zoneInput.value = '';
}
function clearEditMarkup(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(canvas){
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  editTool = null;
  editDrawing = false;
  editLastPoint = null;
  markupUsedBrush = false;
  markupUsedEraser = false;
  closeZoneIntentPanel(true);
  updateEditToolUi();
  const next = document.getElementById('markupNextStep');
  if(next) next.classList.remove('open');
  const panel = document.getElementById('chatStepPanel');
  if(panel) panel.classList.remove('open');
  const card = document.getElementById('chatCard');
  if(card) card.classList.remove('awaiting-instruction');
  const wrap = document.getElementById('chatSendTour');
  if(wrap) wrap.classList.remove('needs-instruction');
  const quick = document.getElementById('quickPrompts');
  if(quick) quick.classList.remove('awaiting');
  const idleNote = document.getElementById('chatIdleNote');
  if(idleNote) idleNote.style.display = '';
}
function markupHasPaint(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !canvas.width || !canvas.height) return false;
  const ctx = canvas.getContext('2d');
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  for(let i = 3; i < data.length; i += 16){
    if(data[i] > 8) return true;
  }
  return false;
}
async function exportEditAnnotationBlob(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !markupHasPaint()) return null;
  const layout = getFinalImageLayout();
  const out = document.createElement('canvas');
  if(layout){
    out.width = Math.max(1, Math.round(layout.nw));
    out.height = Math.max(1, Math.round(layout.nh));
  } else {
    const maxSide = 1600;
    const sw = canvas.width, sh = canvas.height;
    const scale = Math.min(1, maxSide / Math.max(sw, sh));
    out.width = Math.max(1, Math.round(sw * scale));
    out.height = Math.max(1, Math.round(sh * scale));
  }
  const ctx = out.getContext('2d');
  ctx.clearRect(0, 0, out.width, out.height);
  ctx.drawImage(canvas, 0, 0, out.width, out.height);
  return await new Promise((resolve) => out.toBlob((b) => resolve(b || null), 'image/png'));
}
function resetStudioUi(){
  lastState = {};
  editTool = null;
  editDrawing = false;
  editLastPoint = null;
  markupUsedBrush = false;
  markupUsedEraser = false;
  feedbackVote = '';
  feedbackPromptedHistoryId = '';
  feedbackToastDismissedFor = '';
  if(feedbackTimer){ clearTimeout(feedbackTimer); feedbackTimer = null; }

  const dropzone = document.getElementById('dropzone');
  if(dropzone) dropzone.classList.remove('has-image', 'dragover');
  const sourceImg = document.getElementById('sourceImg');
  if(sourceImg){ sourceImg.removeAttribute('src'); sourceImg.src = ''; }
  const finalImg = document.getElementById('finalImg');
  if(finalImg){
    finalImg.onload = null;
    finalImg.removeAttribute('src');
    finalImg.src = '';
  }
  clearEditMarkup();
  setMarkupEnabled(false);

  const hist = document.getElementById('historyStrip');
  if(hist) hist.innerHTML = '<div class="muted">История версий появится после генерации</div>';
  const hint = document.getElementById('activeHistoryHint');
  if(hint) hint.textContent = '';
  renderChat([]);

  const chatInput = document.getElementById('chatInput');
  if(chatInput) chatInput.value = '';
  const sourceFile = document.getElementById('sourceFile');
  if(sourceFile) sourceFile.value = '';

  document.getElementById('downloadBtn').disabled = true;
  const copyBtn = document.getElementById('copyFinalBtn');
  if(copyBtn) copyBtn.disabled = true;
  document.getElementById('chatBtn').disabled = !projectId;
  document.getElementById('startBtn').disabled = !projectId;

  const feedbackZone = document.getElementById('feedbackZone');
  if(feedbackZone) feedbackZone.classList.remove('open', 'required', 'blocking');
  closeFeedbackGate();
  hideFeedbackToast();
  pendingAfterFeedback = null;
  setFeedbackVote('');
  updateEditToolUi();
}
async function resolveStudioImageModel(){
  // Always use server default — ignore stale localStorage (it was pinning old expensive models).
  try{ localStorage.removeItem('niteos_routerai_model'); }catch(_){}
  if(studioImageModel) return studioImageModel;
  try{
    const health = await api('/api/health');
    studioImageModel = String(health.routerai_model || '').trim();
  }catch(_){
    studioImageModel = '';
  }
  return studioImageModel;
}
async function createProject(opts){
  if(!(opts && opts.skipFeedbackGate) && requireFeedbackBeforeAction({type:'createProject'})) return;
  try{
    setBusy(true, 'Создаю новый проект…');
    const body = new URLSearchParams({name:'AI Studio', mode:'agent_studio'});
    if(projectId) body.append('from_project_id', projectId);
    const data = await api('/api/projects', {method:'POST', body});
    projectId = data.id || data.project_id || (data.project && (data.project.id || data.project.project_id)) || '';
    if(!projectId) throw new Error('Не удалось создать проект');
    history.replaceState({}, '', '/studio?project=' + projectId);
    document.getElementById('projectLabel').textContent = 'Проект ' + projectId;
    const dealerLink = document.getElementById('dealerLink');
    if(dealerLink) dealerLink.href = '/dealer?project=' + projectId;
    resetStudioUi();
    syncPhotoWarnVisibility();
    setBusy(false, 'Новый проект пустой. Вставьте фото (Ctrl+V) или выберите файл.');
    return projectId;
  }catch(err){
    if(err.status === 409){
      promptFeedbackRequired(err.message, {type:'createProject'});
    } else {
      setError(String(err.message || err));
    }
    busy = false;
    throw err;
  }
}
async function ensureProject(){
  const id = qs().get('project');
  if(id){
    projectId = id;
    document.getElementById('projectLabel').textContent = 'Проект ' + projectId;
    const dealerLink = document.getElementById('dealerLink');
    if(dealerLink) dealerLink.href = '/dealer?project=' + projectId;
    document.getElementById('startBtn').disabled = false;
    await refreshState();
    syncPhotoWarnVisibility();
    return projectId;
  }
  return createProject();
}
async function refreshState(){
  if(!projectId) return;
  const data = await api(`/api/projects/${projectId}/studio/state`);
  await applyStudioPayload(data);
  // Don't dismiss an in-flight generation overlay here — applyStudioPayload holds it
  // until the new final image is painted.
  if(busy) return;
  if(data.has_source && !data.has_final) setBusy(false, 'Фото есть. Можно запускать анализ → генерацию.');
  if(!data.has_source) setBusy(false, 'Скопируйте фото и нажмите Ctrl+V — или выберите файл');
}
function fileFromClipboardItem(item){
  if(!item) return null;
  if(item.kind === 'file' && item.type && item.type.startsWith('image/')){
    return item.getAsFile();
  }
  return null;
}
async function uploadSourceFile(file){
  if(!file) return;
  if(!String(file.type || '').startsWith('image/')){
    setError('Нужно изображение (PNG/JPG/WebP), не файл другого типа');
    return;
  }
  try{
    if(!projectId) await ensureProject();
    setBusy(true, 'Загрузка фото…');
    const name = file.name || ('paste_' + Date.now() + '.png');
    const fd = new FormData();
    fd.append('file', file, name);
    await api(`/api/projects/${projectId}/source`, {method:'POST', body: fd});
    const zone = document.getElementById('dropzone');
    const img = document.getElementById('sourceImg');
    img.src = URL.createObjectURL(file);
    zone.classList.add('has-image');
    setBusy(false, 'Фото загружено. Нажмите «Анализ → генерация».');
    document.getElementById('startBtn').disabled = false;
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
const dropzone = document.getElementById('dropzone');
const sourceFile = document.getElementById('sourceFile');
let dropzoneLastTap = 0;
function openSourceFilePicker(){
  sourceFile.click();
}
document.getElementById('pickFileBtn').addEventListener('click', (e) => {
  e.preventDefault();
  openSourceFilePicker();
});
// File dialog only after two taps / double-click on the dropzone (not one).
dropzone.addEventListener('click', (e) => {
  const now = Date.now();
  if(now - dropzoneLastTap < 450){
    dropzoneLastTap = 0;
    e.preventDefault();
    openSourceFilePicker();
    return;
  }
  dropzoneLastTap = now;
});
dropzone.addEventListener('dblclick', (e) => {
  // Second click already opens via the timer above; block native dblclick side-effects.
  e.preventDefault();
});
dropzone.addEventListener('keydown', (e) => {
  if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); openSourceFilePicker(); }
});
sourceFile.addEventListener('change', async (e) => {
  const file = e.target.files && e.target.files[0];
  if(file) await uploadSourceFile(file);
  sourceFile.value = '';
});
;['dragenter','dragover'].forEach(ev => {
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); dropzone.classList.add('dragover'); });
});
;['dragleave','drop'].forEach(ev => {
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); dropzone.classList.remove('dragover'); });
});
dropzone.addEventListener('drop', async (e) => {
  const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if(file) await uploadSourceFile(file);
});
async function setFinalFromFile(file){
  if(!projectId || !file) return;
  try{
    setBusy(true, 'Устанавливаю скопированное фото как рабочее…');
    const fd = new FormData();
    fd.append('file', file, file.name || 'pasted_final.png');
    fd.append('note', 'clipboard paste as working final');
    await api(`/api/projects/${projectId}/studio/set-final`, {method:'POST', body: fd});
    clearEditMarkup();
    await refreshState();
    setBusy(false, 'Рабочее фото обновлено. Можно размечать и править.');
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
function pickClipboardImage(e){
  const items = (e.clipboardData && e.clipboardData.items) ? Array.from(e.clipboardData.items) : [];
  for(const item of items){
    const file = fileFromClipboardItem(item);
    if(file) return file;
  }
  if(e.clipboardData && e.clipboardData.files && e.clipboardData.files.length){
    const f = e.clipboardData.files[0];
    if(f && String(f.type || '').startsWith('image/')) return f;
  }
  return null;
}
window.addEventListener('paste', async (e) => {
  const tag = (e.target && e.target.tagName || '').toLowerCase();
  if(tag === 'textarea' || tag === 'input') return;
  const file = pickClipboardImage(e);
  if(!file) return;
  e.preventDefault();
  // If a final already exists, paste becomes the new working render; otherwise source upload.
  if(lastState && lastState.has_final){
    await setFinalFromFile(file);
  } else {
    await uploadSourceFile(file);
  }
});
dropzone.addEventListener('paste', async (e) => {
  e.stopPropagation();
  const file = pickClipboardImage(e);
  if(!file) return;
  e.preventDefault();
  await uploadSourceFile(file);
});
function toggleTip(id){
  document.querySelectorAll('.tip.open').forEach(el => {
    if(el.id !== id) el.classList.remove('open');
  });
  const tip = document.getElementById(id);
  if(tip) tip.classList.toggle('open');
}
document.addEventListener('click', (e) => {
  const t = e.target;
  if(t && (t.closest && t.closest('.tip'))) return;
  document.querySelectorAll('.tip.open').forEach(el => el.classList.remove('open'));
});
function photoCheckStorageKey(){
  return 'niteos_photo_check_ok_' + (projectId || 'none');
}
function hasPhotoCheckPassed(){
  try{ return localStorage.getItem(photoCheckStorageKey()) === '1'; }catch(_){ return false; }
}
function markPhotoCheckPassed(){
  try{ localStorage.setItem(photoCheckStorageKey(), '1'); }catch(_){}
  const soft = document.getElementById('photoSoftWarn');
  if(soft) soft.style.display = 'none';
}
function syncPhotoWarnVisibility(){
  const soft = document.getElementById('photoSoftWarn');
  if(!soft) return;
  soft.style.display = hasPhotoCheckPassed() ? 'none' : '';
}
function openPhotoCheck(){
  document.getElementById('photoCheckModal').classList.add('open');
}
function closePhotoCheck(){
  document.getElementById('photoCheckModal').classList.remove('open');
}
function confirmPhotoCheckAndStart(){
  markPhotoCheckPassed();
  closePhotoCheck();
  runStudioGeneration();
}
async function startStudio(){
  if(!projectId || busy) return;
  if(requireFeedbackBeforeAction({type:'generate'})) return;
  if(!(lastState && lastState.has_source) && !document.getElementById('dropzone').classList.contains('has-image')){
    setError('Сначала загрузите фото фасада');
    return;
  }
  // Подсказка о качестве фото — один раз на проект.
  if(hasPhotoCheckPassed()){
    runStudioGeneration();
    return;
  }
  openPhotoCheck();
}
async function runStudioGeneration(opts){
  if(!projectId || busy) return;
  if(!(opts && opts.skipFeedbackGate) && requireFeedbackBeforeAction({type:'generate'})) return;
  try{
    setBusy(true, 'Анализ фасада… подбор стиля… генерация…');
    const fd = new FormData();
    const model = await resolveStudioImageModel();
    if(model) fd.append('routerai_model', model);
    await api(`/api/projects/${projectId}/studio/start`, {method:'POST', body: fd});
    clearEditMarkup();
    // Overlay stays until refreshState paints the new final image.
    await refreshState();
  }catch(err){
    if(err.status === 409){
      setBusy(false);
      promptFeedbackRequired(err.message, {type:'generate'});
    } else {
      setError(String(err.message || err));
    }
  }
}
async function startStudioLegacy(){
  // kept for safety if anything still calls old name mid-generation
  return runStudioGeneration();
}
async function sendChat(opts){
  if(!projectId || busy) return;
  if(!(opts && opts.skipFeedbackGate) && requireFeedbackBeforeAction({type:'chat'})) return;
  const text = (document.getElementById('chatInput').value || '').trim();
  const annotationBlob = await exportEditAnnotationBlob();
  if(!text && !annotationBlob){
    setError('Напишите, что хотите изменить');
    highlightChatInstruction();
    return;
  }
  if(annotationBlob && !text){
    promptMarkupInstructionNeeded();
    return;
  }
  try{
    setBusy(true, annotationBlob ? 'Агент правит отмеченные светильники по вашему тексту…' : 'Агент правит результат…');
    const fd = new FormData();
    fd.append('message', text);
    const model = await resolveStudioImageModel();
    if(model) fd.append('routerai_model', model);
    if(annotationBlob) fd.append('annotation_file', annotationBlob, 'edit_annotation.png');
    await api(`/api/projects/${projectId}/studio/chat`, {method:'POST', body: fd});
    document.getElementById('chatInput').value = '';
    clearEditMarkup();
    setBusy(true, 'Почти готово — загружаю обновлённый результат…');
    // Overlay stays until the new result image is actually visible.
    await refreshState();
    if(!busy) setBusy(false, 'Правка применена — смотрите результат в центре');
    try{
      document.getElementById('resultCard')?.scrollIntoView({behavior:'smooth', block:'center'});
    }catch(_){}
  }catch(err){
    if(err.status === 409){
      setBusy(false);
      promptFeedbackRequired(err.message, {type:'chat'});
    } else {
      setError(String(err.message || err));
    }
  }
}
function fillChatPrompt(text){
  // Append into chat so brush + eraser presets can be combined; never auto-send.
  const input = document.getElementById('chatInput');
  if(!input) return;
  const next = String(text || '').trim();
  if(!next) return;
  const cur = (input.value || '').trim();
  input.value = cur ? (cur.replace(/\s+$/,'') + '\n' + next) : next;
  const wrap = document.getElementById('chatSendTour');
  if(wrap) wrap.classList.remove('needs-instruction');
  try{ input.focus({preventScroll:true}); }catch(_){ try{ input.focus(); }catch(__){} }
  const box = document.getElementById('statusBox');
  if(box){
    box.classList.remove('busy', 'err');
    box.textContent = markupHasPaint()
      ? 'Шаблон добавлен в чат. Можно дополнить текст и нажать «Отправить».'
      : 'Текст добавлен в чат. Можно отправлять или дополнить.';
  }
  updateMarkupNextStep();
}
// Keep old name as alias without auto-send (in case cached HTML still calls it).
function quickChat(text){
  fillChatPrompt(text);
}
function downloadFinal(){
  if(!projectId) return;
  (async () => {
    try{
      const url = `/api/projects/${projectId}/file/output/final_imported_render.png?t=${Date.now()}`;
      const res = await fetch(url, {credentials:'same-origin'});
      if(!res.ok) throw new Error('Не удалось получить файл');
      const blob = await res.blob();
      const stamp = new Date().toISOString().slice(0,10).replace(/-/g,'');
      const name = `niteos_концепция_${projectId.slice(0,8)}_${stamp}.png`;
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
      setBusy(false, 'Скачано: ' + name);
    }catch(err){
      setError('Скачивание не удалось: ' + String(err.message || err));
    }
  })();
}
async function blobToPng(blob){
  if(blob && blob.type === 'image/png') return blob;
  const bmp = await createImageBitmap(blob);
  const canvas = document.createElement('canvas');
  canvas.width = bmp.width;
  canvas.height = bmp.height;
  canvas.getContext('2d').drawImage(bmp, 0, 0);
  return await new Promise((resolve, reject) => {
    canvas.toBlob((b) => b ? resolve(b) : reject(new Error('PNG convert failed')), 'image/png');
  });
}
async function copyFinal(){
  if(!projectId) return;
  const finalImg = document.getElementById('finalImg');
  const url = (finalImg && finalImg.getAttribute('src'))
    || `/api/projects/${projectId}/file/output/final_imported_render.png?t=${Date.now()}`;
  try{
    const res = await fetch(url, {credentials:'same-origin'});
    if(!res.ok) throw new Error('Не удалось загрузить изображение');
    const raw = await res.blob();
    const png = await blobToPng(raw);
    if(navigator.clipboard && window.ClipboardItem){
      try{
        await navigator.clipboard.write([
          new ClipboardItem({ 'image/png': png })
        ]);
        setBusy(false, 'Фото скопировано в буфер обмена. Вставьте через Ctrl+V.');
        return;
      }catch(clipErr){
        // HTTP / insecure context often blocks clipboard.write for images.
      }
    }
    const href = URL.createObjectURL(png);
    const a = document.createElement('a');
    a.href = href;
    a.download = `niteos_концепция_${projectId.slice(0,8)}_${Date.now()}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
    setBusy(false, 'Буфер недоступен в этом браузере/по HTTP. Файл скачан — откройте и Ctrl+C.');
  }catch(err){
    setError('Копирование не удалось: ' + String(err.message || err));
  }
}
bindMarkupCanvas();
(function bindChatInstructionWatch(){
  const input = document.getElementById('chatInput');
  if(!input) return;
  const sync = () => updateMarkupNextStep();
  input.addEventListener('input', sync);
  input.addEventListener('change', sync);
})();
ensureProject().then(() => {
  syncPhotoWarnVisibility();
  maybeShowWelcomeTour();
}).catch(err => setError(String(err.message || err)));
</script>
</body>
</html>
"""
