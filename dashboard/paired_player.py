"""Synchronized paired player with source-frame timestamp mapping and shared controls."""
from html import escape
import streamlit.components.v1 as components

def build_pair_html(original_url,heatmap_url,timeline_url=None,heatmap_fps=30.0):
    a=escape(original_url,quote=True); b=escape(heatmap_url,quote=True)
    timeline=escape(timeline_url or "",quote=True)
    fps=max(0.1,float(heatmap_fps))
    html=f'''<!doctype html><html><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#0b1220;color:#e5edf8;font:14px Inter,Segoe UI,sans-serif}}
    .wrap{{padding:12px 14px;background:#0f1727;border:1px solid #25334a;border-radius:14px}}
    .videos{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.panel{{min-width:0}}
    .label{{font-size:12px;color:#9eb0c9;letter-spacing:.08em;text-transform:uppercase;margin:0 0 8px}}
    video{{width:100%;max-height:410px;background:#030712;border-radius:10px;display:block;object-fit:contain}}
    .controls{{display:grid;grid-template-columns:auto auto auto minmax(100px,1fr) auto auto;align-items:center;gap:10px;margin-top:12px}}
    button,select{{border:1px solid #34435b;border-radius:8px;background:#17243a;color:#eef5ff;padding:8px 12px;cursor:pointer}}
    input[type=range]{{width:100%;accent-color:#36b7a5}}.time{{font-variant-numeric:tabular-nums;color:#c5d0e0;white-space:nowrap}}
    .hint{{color:#7f93ad;font-size:11px;margin-top:8px}}@media(max-width:680px){{.videos{{grid-template-columns:1fr}}video{{max-height:280px}}.controls{{grid-template-columns:auto auto auto 1fr}}}}
    </style></head><body><div class="wrap"><div class="videos">
      <div class="panel"><div class="label">Original video</div><video id="original" preload="metadata" playsinline src="{a}"></video></div>
      <div class="panel"><div class="label">Movement heatmap · source-frame mapped</div><video id="heatmap" preload="metadata" playsinline src="{b}"></video></div>
    </div><div class="controls"><button id="play" aria-label="Play both videos">▶ Play</button><button id="pause">Ⅱ Pause</button><button id="back">−5s</button>
      <input id="seek" type="range" min="0" max="1000" value="0" aria-label="Seek both videos"><span class="time" id="clock">00:00 / --:--</span>
      <select id="speed" aria-label="Playback speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></div>
      <div class="hint" id="state">Loading videos and source-frame timeline…</div></div>
    <script>
    (()=>{{const a=document.getElementById('original'),b=document.getElementById('heatmap'),seek=document.getElementById('seek'),clock=document.getElementById('clock'),state=document.getElementById('state');
    const timelineUrl="{timeline}";let timeline=null,duration=0,heatFps={fps},readyMap=!timelineUrl,lock=false;
    const fmt=s=>{{if(!Number.isFinite(s))return'--:--';s=Math.max(0,Math.floor(s));return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}};
    function frameAt(t){{const times=timeline&&timeline.source_timestamps_s;if(!times||!times.length)return Math.max(0,Math.min(Math.round(t*heatFps),Math.round(duration*heatFps)));let lo=0,hi=times.length;while(lo<hi){{const mid=(lo+hi)>>1;if(times[mid]<t)lo=mid+1;else hi=mid}}if(lo<=0)return 0;if(lo>=times.length)return times.length-1;return Math.abs(times[lo]-t)<Math.abs(times[lo-1]-t)?lo:lo-1}}
    function targetHeatTime(t){{return Math.max(0,Math.min(frameAt(t)/heatFps,Number.isFinite(b.duration)?b.duration:duration))}}
    function syncHeat(t,force=false){{if(!Number.isFinite(t)||b.readyState<1)return;const target=targetHeatTime(t);if(force||Math.abs(b.currentTime-target)>Math.max(.12,1/heatFps))b.currentTime=target}}
    function ready(){{if(a.readyState>=1&&b.readyState>=1&&readyMap){{duration=a.duration;seek.max=Math.max(1,Math.round(duration*1000));state.textContent=timeline?'Ready · seek uses stored source frame timestamps':'Ready · nominal frame-rate mapping';clock.textContent=fmt(0)+' / '+fmt(duration);syncHeat(0,true)}}}}
    a.addEventListener('loadedmetadata',ready);b.addEventListener('loadedmetadata',ready);
    if(timelineUrl)fetch(timelineUrl).then(r=>{{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}}).then(data=>{{timeline=data;heatFps=Number(data.heatmap_fps)||heatFps;readyMap=true;ready()}}).catch(e=>{{state.textContent='Timeline map unavailable; using nominal frame rate ('+e.message+')';readyMap=true;ready()}});
    document.getElementById('play').onclick=async()=>{{try{{syncHeat(a.currentTime,true);await Promise.all([a.play(),b.play()]);state.textContent='Playing with shared source-frame timing'}}catch(e){{state.textContent='Playback error: '+e.message}}}};
    document.getElementById('pause').onclick=()=>{{a.pause();b.pause();state.textContent='Paused together'}};
    document.getElementById('back').onclick=()=>{{const t=Math.max(0,a.currentTime-5);a.currentTime=t;syncHeat(t,true)}};
    seek.oninput=()=>{{const t=Number(seek.value)/1000;a.currentTime=t;syncHeat(t,true)}};
    document.getElementById('speed').onchange=e=>{{a.playbackRate=Number(e.target.value);b.playbackRate=Number(e.target.value)}};
    a.addEventListener('timeupdate',()=>{{if(lock)return;lock=true;syncHeat(a.currentTime);seek.value=Math.round(a.currentTime*1000);clock.textContent=fmt(a.currentTime)+' / '+fmt(duration);lock=false}});
    a.addEventListener('ended',()=>{{b.pause();state.textContent='Playback ended'}});b.addEventListener('error',()=>{{state.textContent='Heatmap video could not be loaded'}});a.addEventListener('error',()=>{{state.textContent='Original video could not be loaded'}});
    }})();</script></body></html>'''
    return html

def paired_video_player(original_url,heatmap_url,timeline_url=None,heatmap_fps=30.0,*,height=570):
    components.html(build_pair_html(original_url,heatmap_url,timeline_url,heatmap_fps),height=height,scrolling=False)
