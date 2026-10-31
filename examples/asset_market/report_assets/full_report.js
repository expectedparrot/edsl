"use strict";
const REPORT = JSON.parse(document.getElementById("report-data").textContent);
const sessions = REPORT.sessions;
const $ = id => document.getElementById(id);
let sessionIndex = 0, period = 1, selectedTrader = "trader-00", timer = null, ledgerPage = 0;
const pageSize = 25;
const money = n => n == null ? "—" : "$" + Number(n).toFixed(2);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const rowsAll = sessions.flatMap(s => s.rows);
const NS = "http://www.w3.org/2000/svg";
function element(name, attrs = {}, content) {
  const el = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  if (content !== undefined) el.textContent = content;
  return el;
}
function chart(container, xDomain, yDomain, xLabel, yLabel) {
  const width=540, height=300, left=63, right=23, top=22, bottom=50;
  const svg=element("svg",{viewBox:`0 0 ${width} ${height}`,role:"img","aria-label":yLabel+" against "+xLabel});
  const x=v=>left+(v-xDomain[0])/(xDomain[1]-xDomain[0])*(width-left-right);
  const y=v=>height-bottom-(v-yDomain[0])/(yDomain[1]-yDomain[0])*(height-top-bottom);
  for(let i=0;i<=4;i++){
    const v=yDomain[0]+i*(yDomain[1]-yDomain[0])/4;
    svg.append(element("line",{x1:left,x2:width-right,y1:y(v),y2:y(v),stroke:"#e1e8eb"}));
    svg.append(element("text",{x:left-9,y:y(v)+4,"text-anchor":"end","font-size":11,fill:"#5d707b"},v.toFixed(yDomain[1]-yDomain[0]>100?0:1)));
    const xv=xDomain[0]+i*(xDomain[1]-xDomain[0])/4;
    svg.append(element("text",{x:x(xv),y:height-bottom+19,"text-anchor":"middle","font-size":11,fill:"#5d707b"},Number(xv.toFixed(1))));
  }
  svg.append(element("text",{x:width/2,y:height-9,"text-anchor":"middle","font-size":12,fill:"#172e3a"},xLabel));
  svg.append(element("text",{transform:`translate(15 ${height/2}) rotate(-90)`,"text-anchor":"middle","font-size":12,fill:"#172e3a"},yLabel));
  $(container).replaceChildren(svg);
  return {svg,x,y,left,right,width,height};
}
function line(c, points, color, dashed=false) {
  c.svg.append(element("polyline",{points:points.map(([x,y])=>`${c.x(x)},${c.y(y)}`).join(" "),fill:"none",stroke:color,"stroke-width":2,"stroke-dasharray":dashed?"5 4":"none"}));
}
function renderBook(s) {
  const b=s.books[period-1], values=[...b.bid_units,...b.ask_units,14];
  const lower=Math.max(0,Math.min(...values)-1), upper=Math.max(...values)+1;
  const maxUnits=Math.max(2,b.bid_units.length,b.ask_units.length);
  const c=chart("book-chart",[0,maxUnits+.5],[lower,upper],"Cumulative unit rank","Limit price ($)");
  for(const [units,color,label] of [[b.bid_units,"#087e8b","Buy"],[b.ask_units,"#ce6c2b","Sell"]]) {
    const points=[];
    units.forEach((value,i)=>{points.push([i+.5,value],[i+1.5,value]);});
    if(points.length)line(c,points,color);
    units.forEach((value,i)=>{
      const dot=element("circle",{cx:c.x(i+1),cy:c.y(value),r:3,fill:color});
      dot.append(element("title",{},`${label} unit ${i+1}: ${money(value)}`));c.svg.append(dot);
    });
  }
  if(b.price!=null)line(c,[[0,b.price],[maxUnits+.5,b.price]],"#172e3a",true);
  c.svg.append(element("text",{x:80,y:20,"font-size":12,fill:"#087e8b"},`Buy: ${b.bid_units.length} units`));
  c.svg.append(element("text",{x:250,y:20,"font-size":12,fill:"#ce6c2b"},`Sell: ${b.ask_units.length} units`));
  if(!b.bid_units.length&&!b.ask_units.length)c.svg.append(element("text",{x:280,y:145,"text-anchor":"middle","font-size":17,fill:"#5d707b"},"No active admitted orders"));
}
function renderTrader(s) {
  const rows=s.rows.filter(r=>r.trader===selectedTrader), row=rows.find(r=>r.period===period);
  const c=chart("trader-chart",[0,30],[0,Math.max(8,...rows.map(r=>r.closing_shares_before_redemption))+1],"Market period","Shares held before redemption");
  const points=[[0,4]];
  rows.forEach(r=>{points.push([r.period,points[points.length-1][1]],[r.period,r.closing_shares_before_redemption]);});
  line(c,points,"#087e8b");
  c.svg.append(element("line",{x1:c.x(period),x2:c.x(period),y1:25,y2:250,stroke:"#ce6c2b","stroke-dasharray":"4 3"}));
  c.svg.append(element("text",{x:78,y:20,"font-size":12,fill:"#172e3a"},`Period ${period} closing cash: ${money(row.closing_cash_before_redemption)}`));
  $("trader-heading").textContent=`${selectedTrader} · ${row.persona} · period ${period}`;
  $("trader-forecasts").textContent=`Forecasts: now ${money(row.forecast_0)} · +2 ${money(row.forecast_2)} · +5 ${money(row.forecast_5)} · +10 ${money(row.forecast_10)}`;
  $("trader-rationale").textContent=row.rationale;
}
function renderReplay() {
  const s=sessions[sessionIndex], b=s.books[period-1];
  $("period-range").value=period;$("period-label").textContent=period;
  $("previous-period").disabled=period===1;$("next-period").disabled=period===30;
  $("replay-summary").textContent=`${s.config.treatment} · period ${period}: ${b.volume} shares traded${b.price==null?"":` at ${money(b.price)}`} · ${b.reason}. Best admitted bid ${money(b.best_bid)}; best admitted ask ${money(b.best_ask)}.`;
  const body=$("period-table").querySelector("tbody");body.replaceChildren();
  s.rows.filter(r=>r.period===period).forEach(r=>{
    const tr=document.createElement("tr");tr.tabIndex=0;tr.dataset.trader=r.trader;
    if(r.trader===selectedTrader)tr.className="selected";
    tr.innerHTML=`<td>${esc(r.trader)}<br><small>${esc(r.persona)}</small></td><td class="${esc(r.side)}">${esc(r.side)}</td><td>${r.side==="hold"?"—":money(r.limit_price)}</td><td>${r.submitted_quantity} / ${r.admitted_quantity}</td><td>${r.signed_fill>0?"+":""}${r.signed_fill}</td><td>${money(r.opening_cash)} → ${money(r.closing_cash_before_redemption)}</td><td>${r.opening_shares} → ${r.closing_shares_before_redemption}</td>`;
    const choose=()=>{selectedTrader=r.trader;renderReplay();};
    tr.onclick=choose;tr.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose();}};
    body.append(tr);
  });
  renderBook(s);renderTrader(s);
}
function filteredRows() {
  const query=$("ledger-search").value.trim().toLowerCase(),side=$("ledger-side").value,filled=$("fills-only").checked;
  return rowsAll.filter(r=>(!side||r.side===side)&&(!filled||r.signed_fill!==0)&&(!query||`${r.condition} ${r.trader} ${r.persona} ${r.period} ${r.rationale}`.toLowerCase().includes(query)));
}
function renderLedger() {
  const rows=filteredRows(),pages=Math.max(1,Math.ceil(rows.length/pageSize));ledgerPage=Math.min(ledgerPage,pages-1);
  $("ledger-count").textContent=`${rows.length.toLocaleString()} of ${rowsAll.length.toLocaleString()} decisions match. One record per trader per period.`;
  $("ledger-page").textContent=`Page ${ledgerPage+1} of ${pages}`;
  $("ledger-prev").disabled=ledgerPage===0;$("ledger-next").disabled=ledgerPage>=pages-1;
  $("ledger-table").querySelector("tbody").innerHTML=rows.slice(ledgerPage*pageSize,(ledgerPage+1)*pageSize).map(r=>`<tr><td>${esc(r.condition)}<br>${esc(r.trader)} · ${esc(r.persona)}</td><td>${r.period}</td><td class="${esc(r.side)}">${esc(r.side)}</td><td>${r.side==="hold"?"—":money(r.limit_price)}</td><td>${r.submitted_quantity} / ${r.admitted_quantity}</td><td>${r.signed_fill>0?"+":""}${r.signed_fill}</td><td><details><summary>Forecasts & rationale</summary><p>Now ${money(r.forecast_0)} · +2 ${money(r.forecast_2)} · +5 ${money(r.forecast_5)} · +10 ${money(r.forecast_10)}.</p><p>${esc(r.rationale)}</p><p>Execution: ${money(r.execution_price)}. Closing cash ${money(r.closing_cash_before_redemption)}; shares ${r.closing_shares_before_redemption}.</p></details></td></tr>`).join("");
}
sessions.forEach((s,i)=>{const option=document.createElement("option");option.value=i;option.textContent=s.config.treatment+" · seed "+s.config.seed;$("session-select").append(option);});
$("session-select").onchange=e=>{sessionIndex=Number(e.target.value);renderReplay();};
$("period-range").oninput=e=>{period=Number(e.target.value);renderReplay();};
$("previous-period").onclick=()=>{period=Math.max(1,period-1);renderReplay();};
$("next-period").onclick=()=>{period=Math.min(30,period+1);renderReplay();};
$("play").onclick=()=>{
  if(timer){clearInterval(timer);timer=null;$("play").textContent="Play";return;}
  $("play").textContent="Pause";
  timer=setInterval(()=>{if(period>=30){clearInterval(timer);timer=null;$("play").textContent="Play";}else{period++;renderReplay();}},850);
};
for(const id of ["ledger-search","ledger-side","fills-only"])$(id).addEventListener("input",()=>{ledgerPage=0;renderLedger();});
$("ledger-prev").onclick=()=>{ledgerPage--;renderLedger();};
$("ledger-next").onclick=()=>{ledgerPage++;renderLedger();};
window.addEventListener("beforeprint",()=>document.querySelectorAll("#personas details").forEach(d=>d.open=true));
renderReplay();renderLedger();
