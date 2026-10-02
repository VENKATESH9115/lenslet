const $=s=>document.querySelector(s),inr=n=>"₹"+Math.round(n).toLocaleString("en-IN");
const camSvg='<svg viewBox="0 0 100 80" fill="none" stroke="#ffa77a" stroke-width="2.4" stroke-linejoin="round"><rect x="8" y="22" width="84" height="48" rx="9"/><path d="M34 22l5-10h22l5 10"/><circle cx="50" cy="46" r="15"/><circle cx="50" cy="46" r="6" fill="#ffa77a" stroke="none"/></svg>';
const lensSvg='<svg viewBox="0 0 100 80" fill="none" stroke="#ffa77a" stroke-width="2.4"><rect x="22" y="14" width="56" height="52" rx="8"/><path d="M22 28h56M22 52h56"/><circle cx="50" cy="40" r="0.1"/></svg>';
const gimSvg='<svg viewBox="0 0 100 80" fill="none" stroke="#ffa77a" stroke-width="2.4" stroke-linecap="round"><path d="M50 8v18M30 26h40v22H30zM50 48v22M38 70h24"/></svg>';
const micSvg='<svg viewBox="0 0 100 80" fill="none" stroke="#ffa77a" stroke-width="2.4" stroke-linecap="round"><rect x="40" y="8" width="20" height="38" rx="10"/><path d="M30 38a20 20 0 0040 0M50 58v14M38 72h24"/></svg>';
const lightSvg='<svg viewBox="0 0 100 80" fill="none" stroke="#ffa77a" stroke-width="2.4" stroke-linecap="round"><circle cx="50" cy="34" r="22"/><path d="M50 56v16M36 72h28M50 22v24"/></svg>';
const droneSvg='<svg viewBox="0 0 100 80" fill="none" stroke="#ffa77a" stroke-width="2.4" stroke-linecap="round"><rect x="38" y="30" width="24" height="16" rx="5"/><path d="M38 34L16 18M62 34l22-16M38 42L16 58M62 42l22 16"/><circle cx="14" cy="16" r="7"/><circle cx="86" cy="16" r="7"/><circle cx="14" cy="60" r="7"/><circle cx="86" cy="60" r="7"/></svg>';
const triSvg='<svg viewBox="0 0 100 80" fill="none" stroke="#ffa77a" stroke-width="2.4" stroke-linecap="round"><path d="M50 10v30M50 40L26 72M50 40l24 32M50 40V72"/><rect x="40" y="6" width="20" height="10" rx="3"/></svg>';
const G=[
{n:"Sony A7 IV",b:"Sony",s:"33MP full-frame · 4K 60p",p:2800,r:4.9,c:128,i:camSvg,bk:[[2,5]]},
{n:"Sony FX3",b:"Sony",s:"Cinema line · 4K 120p",p:4500,r:4.9,c:86,i:camSvg,bk:[[0,3],[8,11]]},
{n:"Canon R6 Mark II",b:"Canon",s:"24MP · 6K RAW oversampled",p:3000,r:4.8,c:74,i:camSvg,bk:[]},
{n:"Sony 24-70mm f/2.8 GM II",b:"Sony",s:"Standard zoom · E-mount",p:1500,r:4.9,c:102,i:lensSvg,bk:[[4,7]]},
{n:"Sony 70-200mm f/2.8 GM II",b:"Sony",s:"Telephoto zoom · E-mount",p:1800,r:4.9,c:67,i:lensSvg,bk:[],m:[[6,9]]},
{n:"DJI RS 4",b:"DJI",s:"3-axis gimbal · 3 kg payload",p:1200,r:4.8,c:59,i:gimSvg,bk:[[1,2]]},
{n:"Rode Wireless PRO",b:"Rode",s:"32-bit float · dual transmitter",p:900,r:4.9,c:91,i:micSvg,bk:[]},
{n:"Godox SL60",b:"Godox",s:"60W LED · Bowens mount",p:600,r:4.7,c:48,i:lightSvg,bk:[[9,12]]},
{n:"DJI Mini 4 Pro",b:"DJI",s:"Under 249 g · 4K HDR",p:2200,r:4.8,c:53,i:droneSvg,bk:[]},
{n:"Manfrotto 190 Tripod",b:"Manfrotto",s:"Carbon fibre · fluid head",p:500,r:4.7,c:44,i:triSvg,bk:[]}];
const today=new Date();today.setHours(0,0,0,0);
const off=d=>Math.round((new Date(d+"T00:00")-today)/864e5);
const iso=n=>{const d=new Date(today.getTime()+n*864e5);return d.toISOString().slice(0,10)};
function status(g,a,b){const t=[...(g.m||[]).map(x=>["Maintenance",x]),...g.bk.map(x=>["Booked",x])];
  if(a==null)return(g.m||[]).length&&g.m[0][0]<=0&&g.m[0][1]>=0?"Maintenance":g.bk.some(x=>x[0]<=0&&x[1]>=0)?"Booked":"Available";
  for(const[s,x]of t)if(a<=x[1]&&b>=x[0])return s;return"Available"}
let rng=null;
function renderGear(){$("#gg").innerHTML=G.slice(0,8).map(g=>{const s=status(g,rng&&rng[0],rng&&rng[1]);
 return`<article class="gear rvl in"><div class="im">${g.i}<span class="st ${s}">${s}</span></div><div class="bd"><span class="br">${g.b}</span><h3>${g.n}</h3><span class="sp">${g.s}</span><span class="rt"><b>★</b> ${g.r} (${g.c})</span><div class="ft"><span class="pr">${inr(g.p)}<small> /day</small></span><a class="btn" style="padding:9px 16px;font-size:14px" href="/gear.html" aria-label="View details for ${g.n}">View Details</a></div></div></article>`}).join("")}
renderGear();
const C=[["Cameras","12 items"],["Lenses","18 items"],["Gimbals","6 items"],["Tripods","9 items"],["Lighting","14 items"],["Microphones","8 items"],["Monitors","5 items"],["Drones","4 items"],["Accessories","40+ items"],["Complete Kits","7 kits"]];
const ic=['<rect x="3" y="7" width="18" height="12" rx="3"/><circle cx="12" cy="13" r="3.5"/>','<rect x="7" y="4" width="10" height="16" rx="2"/><path d="M7 9h10M7 15h10"/>','<path d="M12 3v5M7 8h10v7H7zM12 15v6"/>','<path d="M12 4v8l-6 8M12 12l6 8M12 12v8"/>','<circle cx="12" cy="10" r="6"/><path d="M12 16v5M8 21h8"/>','<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M6 11a6 6 0 0012 0M12 17v4"/>','<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M9 21h6"/>','<rect x="9" y="10" width="6" height="4" rx="1"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/>','<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="9"/>','<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M8 8V5h8v3"/>'];
$("#cc").innerHTML=C.map((c,i)=>`<a class="cat rvl" href="#gear"><svg viewBox="0 0 24 24" aria-hidden="true">${ic[i]}</svg><div><b>${c[0]}</b><small>${c[1]}</small></div></a>`).join("");
/* availability */
const d1=$("#d1"),d2=$("#d2"),msg=$("#msg");d1.min=d2.min=iso(0);
function say(t,c){msg.textContent=t;msg.className="msg "+(c||"")}
$("#chk").addEventListener("submit",e=>{e.preventDefault();
 if(!d1.value||!d2.value)return say("Choose both a pickup and a return date.","e");
 const a=off(d1.value),b=off(d2.value);
 if(a<0||b<0)return say("That date has passed. Choose today or later.","e");
 if(b<a)return say("Return must be on or after the pickup date.","e");
 rng=[a,b];renderGear();
 const free=G.filter(g=>status(g,a,b)==="Available").length;
 say(free?`${free} of ${G.length} items are free for those ${b-a+1} day(s). Cards below are updated.`:"Nothing is free for those dates. Try shifting by a day or two.",free?"k":"e");
 if(free)$("#gear").scrollIntoView()});
$("#ca").addEventListener("click",e=>{e.preventDefault();d1.focus();window.scrollTo({top:0,behavior:"smooth"})});
/* kit */
const K={Camera:[["Sony A7 IV",2800],["Sony FX3",4500],["Canon R6 Mark II",3000]],Lens:[["24-70mm GM II",1500],["70-200mm GM II",1800]],Audio:[["Rode Wireless PRO",900]],Lighting:[["Godox SL60",600]],Stabilisation:[["DJI RS 4",1200],["Manfrotto 190 Tripod",500]],Accessories:[["ND filter set",300],["V-mount battery",400],["Cage and rig",450]]};
const sel={},DEP=.2;let days=2,del=0;
$("#op").innerHTML=Object.entries(K).map(([g,it])=>`<div class="grp"><h3>${g}</h3><div class="chips">${it.map((x,i)=>`<button class="chip" aria-pressed="false" data-g="${g}" data-i="${i}">${x[0]}<small>${inr(x[1])}</small></button>`).join("")}</div></div>`).join("")
 +`<div class="grp"><h3>Delivery</h3><div class="chips" id="dv">${[["Self pickup",0],["Home delivery",350],["Shoot location",600]].map((x,i)=>`<button class="chip" aria-pressed="${i==0}" data-v="${x[1]}">${x[0]}<small>${x[1]?inr(x[1]):"Free"}</small></button>`).join("")}</div></div>`;
$("#op").addEventListener("click",e=>{const c=e.target.closest(".chip");if(!c)return;
 if(c.dataset.v!==undefined){document.querySelectorAll("#dv .chip").forEach(x=>x.setAttribute("aria-pressed",x===c));del=+c.dataset.v}
 else{const g=c.dataset.g,on=c.getAttribute("aria-pressed")==="true";
  document.querySelectorAll(`[data-g="${g}"]`).forEach(x=>x.setAttribute("aria-pressed","false"));
  if(g==="Accessories"){c.setAttribute("aria-pressed",!on);(sel[g]=sel[g]||{})[c.dataset.i]=!on}
  else{c.setAttribute("aria-pressed",!on);sel[g]=on?null:+c.dataset.i}
  if(g==="Accessories")document.querySelectorAll('[data-g="Accessories"]').forEach(x=>x.setAttribute("aria-pressed",!!(sel[g]||{})[x.dataset.i]))}
 calc()});
$("#dm").onclick=()=>{days=Math.max(1,days-1);calc()};$("#dp").onclick=()=>{days=Math.min(30,days+1);calc()};
function calc(){const items=[];
 for(const g in K){if(g==="Accessories"){for(const i in sel[g]||{})if(sel[g][i])items.push(K[g][i])}else if(sel[g]!=null)items.push(K[g][sel[g]])}
 const day=items.reduce((s,x)=>s+x[1],0),base=day*days,pct=(items.length>=4?.1:0)+(days>=3?.05:0),disc=base*pct,tax=(base-disc+del)*.18,dep=day*DEP*5,tot=base-disc+del+tax;
 $("#dn").textContent=days;$("#dl").textContent=days===1?"Rental day":"Rental days";
 $("#kv").innerHTML=items.length?items.map(x=>`<span>${x[0]}</span>`).join(""):'<span style="background:none;color:var(--mut);padding:0">No gear selected yet</span>';
 $("#bk").innerHTML=[["Rental ("+items.length+" items × "+days+"d)",inr(base)],["Discount"+(pct?" "+Math.round(pct*100)+"%":""),"− "+inr(disc)],["Delivery",del?inr(del):"Free"],["GST 18%",inr(tax)],["Refundable deposit",inr(dep)]].map(r=>`<div class="row"><span>${r[0]}</span><b>${r[1]}</b></div>`).join("")+`<div class="row t"><span>Pay now</span><b>${inr(tot+dep)}</b></div>`;
 const ok=sel.Camera!=null;$("#rs").disabled=!ok;$("#rs").style.opacity=ok?1:.5;
 $("#nt").textContent=ok?"Next: choose dates and confirm. Nothing is charged yet.":"Choose at least a camera to continue.";}
$("#rs").onclick=()=>{if(sel.Camera!=null)location.href='/gear.html'};
sel.Camera=0;sel.Lens=0;document.querySelector('[data-g="Camera"][data-i="0"]').setAttribute("aria-pressed","true");document.querySelector('[data-g="Lens"][data-i="0"]').setAttribute("aria-pressed","true");calc();
/* timeline */
const dn=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
let h='<div class="tr"><span></span><div class="bars">'+Array.from({length:14},(_,i)=>`<span>${dn[(today.getDay()+i)%7]}</span>`).join("")+"</div></div>";
G.slice(0,7).forEach(g=>{const seg=[...g.bk.map(x=>[x,""]),...(g.m||[]).map(x=>[x,"mt"])].map(([x,c])=>`<i class="bk ${c}" style="left:${x[0]/14*100}%;width:${(x[1]-x[0]+1)/14*100}%"></i>`).join("");
 h+=`<div class="tr"><span>${g.n}</span><div class="bars">${seg}</div></div>`});
$("#ti").innerHTML=h;
/* header, menu */
const hd=$("#hd");addEventListener("scroll",()=>hd.classList.toggle("s",scrollY>20),{passive:true});
const bg=$("#bg"),dr=$("#dr");
function tog(o){bg.setAttribute("aria-expanded",o);dr.classList.toggle("o",o);dr.setAttribute("aria-hidden",!o);document.body.style.overflow=o?"hidden":""}
bg.onclick=()=>tog(bg.getAttribute("aria-expanded")!=="true");dr.querySelectorAll("a").forEach(a=>a.onclick=()=>tog(false));
addEventListener("keydown",e=>{if(e.key==="Escape")tog(false)});
/* reveal */
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}}),{threshold:.15});
document.querySelectorAll(".rvl,.tl").forEach((el,i)=>{el.style.transitionDelay=el.classList.contains("cat")?(i%5)*60+"ms":"0ms";io.observe(el)});
/* hero parallax + aperture */
const rm=matchMedia("(prefers-reduced-motion:reduce)").matches,cam=$("#cam"),ly=cam.querySelectorAll(".ly"),bl=$("#bl");
if(!rm){addEventListener("pointermove",e=>{const x=(e.clientX/innerWidth-.5),y=(e.clientY/innerHeight-.5);
  ly.forEach(l=>l.style.transform=`translate(${x*l.dataset.d*-2}px,${y*l.dataset.d*-2}px)`)},{passive:true});
 addEventListener("scroll",()=>{bl.style.transform=`rotate(${scrollY*.25}deg) scale(${1-Math.min(scrollY,500)/1800})`;cam.style.transform=`translateY(${scrollY*.12}px)`},{passive:true})}
