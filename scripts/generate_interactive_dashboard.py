"""Build a standalone, interactive BI dashboard from the SQLite model."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "delivery_operations.db"
OUTPUT = ROOT / "powerbi" / "delivery_operations_dashboard.html"


def fetch_all(connection: sqlite3.Connection, sql: str) -> list[dict]:
    cursor = connection.execute(sql)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def load_data() -> dict:
    with sqlite3.connect(DB) as connection:
        return {
            "summary": fetch_all(
                connection,
                """
                SELECT SUBSTR(order_date,1,4) AS year,
                       SUBSTR(order_date,1,7) AS month,
                       city, employment_type,
                       COUNT(*) AS orders,
                       COUNT(DISTINCT rider_id) AS riders,
                       SUM(delivery_cost) AS cost,
                       SUM(revenue) AS revenue,
                       SUM(profit) AS profit,
                       SUM(delivery_distance_km) AS distance,
                       SUM(delivery_time_minutes) AS minutes,
                       SUM(expected_payout) AS expected_payout,
                       SUM(actual_payout) AS actual_payout,
                       SUM(payout_variance) AS variance,
                       SUM(is_cost_anomaly) AS anomalies
                FROM delivery_metrics
                GROUP BY year, month, city, employment_type
                ORDER BY month, city, employment_type
                """,
            ),
            "riders": fetch_all(
                connection,
                """
                SELECT SUBSTR(rdm.metric_date,1,4) AS year,
                       rdm.city, rdm.employment_type, rdm.rider_id,
                       r.rider_name, r.vehicle_type,
                       SUM(rdm.orders_delivered) AS orders,
                       SUM(rdm.shift_hours) AS shift_hours,
                       SUM(rdm.active_delivery_hours) AS active_hours,
                       SUM(rdm.delivery_cost) AS cost,
                       SUM(rdm.revenue) AS revenue
                FROM rider_daily_metrics rdm
                JOIN riders r ON r.rider_id=rdm.rider_id
                GROUP BY year, rdm.city, rdm.employment_type, rdm.rider_id,
                         r.rider_name, r.vehicle_type
                """,
            ),
            "anomalies": fetch_all(
                connection,
                """
                SELECT order_id, order_date, city, employment_type, rider_id,
                       vehicle_type, delivery_distance_km, expected_payout,
                       actual_payout, payout_variance, delivery_cost
                FROM delivery_metrics
                WHERE is_cost_anomaly=1
                ORDER BY delivery_cost DESC
                """,
            ),
        }


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delivery Operations Analytics Dashboard</title>
<style>
:root{--bg:#07101d;--panel:#101e31;--panel2:#14253c;--line:#243a57;--text:#eef4fb;--muted:#8fa5bf;--teal:#42d9ad;--blue:#5ca9ff;--amber:#f7bb59;--red:#ef7180}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;font-size:14px}
button,select{font:inherit}.app{display:grid;grid-template-columns:232px 1fr;min-height:100vh}
.sidebar{background:#0b1728;border-right:1px solid var(--line);padding:25px 18px;position:sticky;top:0;height:100vh}
.brand{display:flex;align-items:center;gap:12px;margin:0 7px 34px}.logo{width:40px;height:40px;border-radius:11px;background:linear-gradient(135deg,var(--teal),var(--blue));display:grid;place-items:center;color:#07101d;font-weight:900;font-size:21px}.brand h1{font-size:15px;margin:0}.brand span{color:var(--muted);font-size:11px}
.nav{display:grid;gap:8px}.nav button{width:100%;border:0;background:transparent;color:var(--muted);padding:13px 14px;text-align:left;border-radius:10px;cursor:pointer}.nav button.active,.nav button:hover{background:var(--panel2);color:#fff}.nav b{display:inline-block;width:27px;color:var(--blue)}
.side-note{position:absolute;bottom:22px;left:25px;right:25px;color:var(--muted);font-size:11px;line-height:1.6;border-top:1px solid var(--line);padding-top:18px}
main{padding:25px 30px 40px;min-width:0}.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}.title h2{font-size:27px;margin:0 0 5px}.title p{margin:0;color:var(--muted)}
.filters{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.filter{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:7px 11px;color:var(--muted)}select{background:transparent;color:var(--text);border:0;outline:0;margin-left:6px}select option{background:#14253c}
.page{display:none}.page.active{display:block}.cards{display:grid;grid-template-columns:repeat(5,minmax(145px,1fr));gap:14px;margin-bottom:14px}.card,.visual{background:linear-gradient(150deg,var(--panel2),var(--panel));border:1px solid #1c314d;border-radius:14px;box-shadow:0 9px 28px #02071155}.card{padding:18px;min-height:111px;position:relative;overflow:hidden}.card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent,var(--teal))}.card .label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.7px}.card .value{font-size:28px;font-weight:750;margin:12px 0 2px}.card .sub{font-size:11px;color:var(--muted)}
.grid2{display:grid;grid-template-columns:1.65fr 1fr;gap:14px;margin-bottom:14px}.grid-equal{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}.visual{padding:18px;min-height:330px}.visual h3{font-size:15px;margin:0}.visual .hint{font-size:11px;color:var(--muted);margin-top:4px}.chart{height:245px;margin-top:15px;position:relative}.chart svg{width:100%;height:100%;overflow:visible}.axis{stroke:#2b405b;stroke-width:1}.gridline{stroke:#20344e;stroke-width:1}.chart-label{fill:#8299b5;font-size:10px}.tooltip{position:fixed;pointer-events:none;background:#07101df2;border:1px solid #334d6d;border-radius:8px;padding:9px 11px;color:#fff;font-size:12px;display:none;z-index:20;box-shadow:0 8px 30px #0008}
.legend{display:flex;gap:18px;margin-top:8px;color:var(--muted);font-size:11px}.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
.barrow{display:grid;grid-template-columns:115px 1fr 58px;gap:10px;align-items:center;margin:12px 0}.bartrack{height:10px;border-radius:8px;background:#20344e;overflow:hidden}.barfill{height:100%;border-radius:8px;background:linear-gradient(90deg,var(--blue),var(--teal))}
.table-wrap{overflow:auto;max-height:306px;margin-top:14px}table{width:100%;border-collapse:collapse;font-size:12px}th{position:sticky;top:0;background:#13243a;color:var(--muted);text-transform:uppercase;font-size:10px;letter-spacing:.6px;text-align:left}th,td{padding:11px 10px;border-bottom:1px solid #20344e;white-space:nowrap}tbody tr:hover{background:#172b45}.badge{display:inline-block;padding:4px 7px;border-radius:8px;background:#283d58}.bad{background:#542632;color:#ff9daa}.good{background:#153e38;color:#75ebc9}
.donut-wrap{display:grid;grid-template-columns:1fr 1fr;align-items:center;height:245px}.donut{width:170px;height:170px;border-radius:50%;margin:auto;display:grid;place-items:center}.donut:after{content:"";width:108px;height:108px;border-radius:50%;background:var(--panel);position:absolute}.donut-center{position:absolute;z-index:1;text-align:center}.donut-center b{display:block;font-size:25px}.donut-center span{color:var(--muted);font-size:10px}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:14px}.compare-box{padding:18px;border-radius:12px;background:#0d1a2b;border:1px solid var(--line)}.compare-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.compare-head b{font-size:20px}.metric-row{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #20344e}.metric-row:last-child{border:0}.empty{color:var(--muted);display:grid;place-items:center;height:220px}
@media(max-width:1100px){.app{grid-template-columns:82px 1fr}.brand h1,.brand span,.nav button span,.side-note{display:none}.sidebar{padding:22px 12px}.nav b{width:auto}.nav button{text-align:center}.cards{grid-template-columns:repeat(3,1fr)}}@media(max-width:760px){.app{display:block}.sidebar{height:auto;position:static;padding:10px}.brand{display:none}.nav{grid-template-columns:repeat(4,1fr)}.nav button{font-size:11px;padding:9px 3px}.nav b{display:none}main{padding:18px}.topbar{display:block}.filters{justify-content:flex-start;margin-top:15px}.cards{grid-template-columns:1fr 1fr}.grid2,.grid-equal,.compare{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
  <div class="brand"><div class="logo">D</div><div><h1>Delivery Ops</h1><span>Analytics command center</span></div></div>
  <nav class="nav">
    <button class="active" data-page="executive"><b>01</b><span>Executive Summary</span></button>
    <button data-page="riders"><b>02</b><span>Rider Analytics</span></button>
    <button data-page="fleet"><b>03</b><span>1P vs 3P</span></button>
    <button data-page="cost"><b>04</b><span>Cost Control</span></button>
  </nav>
  <div class="side-note">Portfolio dashboard<br>SQLite + Python Analytics<br>Data through Dec 2025</div>
</aside>
<main>
  <div class="topbar">
    <div class="title"><h2 id="pageTitle">Executive Summary</h2><p id="pageSubtitle">Network health, unit economics, and delivery volume</p></div>
    <div class="filters">
      <label class="filter">Year<select id="yearFilter"><option value="All">All</option><option>2024</option><option>2025</option></select></label>
      <label class="filter">City<select id="cityFilter"><option value="All">All cities</option></select></label>
      <label class="filter">Fleet<select id="fleetFilter"><option value="All">1P + 3P</option><option>1P</option><option>3P</option></select></label>
    </div>
  </div>

  <section id="executive" class="page active">
    <div class="cards" id="execCards"></div>
    <div class="grid2">
      <div class="visual"><h3>Monthly Cost Per Delivery</h3><div class="hint">Delivery cost divided by completed orders</div><div class="chart" id="cpdChart"></div></div>
      <div class="visual"><h3>Orders by City</h3><div class="hint">Completed delivery contribution</div><div id="cityBars"></div></div>
    </div>
    <div class="grid-equal">
      <div class="visual"><h3>Monthly Order Volume</h3><div class="hint">Completed delivery trend</div><div class="chart" id="ordersChart"></div></div>
      <div class="visual"><h3>Revenue and Delivery Cost</h3><div class="hint">Allocated revenue versus operating cost</div><div class="chart" id="financeChart"></div><div class="legend"><span><i class="dot" style="background:var(--teal)"></i>Revenue</span><span><i class="dot" style="background:var(--amber)"></i>Cost</span></div></div>
    </div>
  </section>

  <section id="riders" class="page">
    <div class="cards" id="riderCards"></div>
    <div class="grid-equal">
      <div class="visual"><h3>Top Riders by Productivity</h3><div class="hint">Orders per planned shift hour</div><div class="table-wrap"><table id="topRiders"></table></div></div>
      <div class="visual"><h3>Riders Requiring Attention</h3><div class="hint">Lowest productivity with at least 20 orders</div><div class="table-wrap"><table id="bottomRiders"></table></div></div>
    </div>
    <div class="grid2">
      <div class="visual"><h3>Productivity Distribution</h3><div class="hint">Rider count by orders-per-hour band</div><div class="chart" id="productivityChart"></div></div>
      <div class="visual"><h3>Vehicle Mix</h3><div class="hint">Riders by primary vehicle</div><div id="vehicleBars"></div></div>
    </div>
  </section>

  <section id="fleet" class="page">
    <div class="cards" id="fleetCards"></div>
    <div class="visual" style="margin-bottom:14px"><h3>Operating Model Scorecard</h3><div class="hint">Side-by-side performance using the selected year and city</div><div class="compare" id="fleetCompare" style="margin-top:18px"></div></div>
    <div class="grid-equal">
      <div class="visual"><h3>Monthly CPD by Fleet</h3><div class="hint">Unit-cost comparison</div><div class="chart" id="fleetCpdChart"></div><div class="legend"><span><i class="dot" style="background:var(--teal)"></i>1P</span><span><i class="dot" style="background:var(--amber)"></i>3P</span></div></div>
      <div class="visual"><h3>Order Share</h3><div class="hint">Completed deliveries by operating model</div><div class="donut-wrap" id="fleetDonut"></div></div>
    </div>
  </section>

  <section id="cost" class="page">
    <div class="cards" id="costCards"></div>
    <div class="grid2">
      <div class="visual"><h3>Monthly Payout Variance</h3><div class="hint">Actual payout minus expected rate-card payout</div><div class="chart" id="varianceChart"></div></div>
      <div class="visual"><h3>Cost Anomalies by City</h3><div class="hint">Deliveries above mean + 2 standard deviations</div><div id="anomalyBars"></div></div>
    </div>
    <div class="visual"><h3>Highest-Cost Deliveries</h3><div class="hint">Audit queue sorted by total delivery cost</div><div class="table-wrap"><table id="anomalyTable"></table></div></div>
  </section>
</main>
</div>
<div class="tooltip" id="tooltip"></div>
<script>
const DATA=__DATA__;
const $=id=>document.getElementById(id), money=n=>"₹"+Math.round(n).toLocaleString("en-IN"), decimal=(n,d=2)=>Number(n||0).toFixed(d), compact=n=>Intl.NumberFormat("en-IN",{notation:"compact",maximumFractionDigits:1}).format(n||0);
const colors={teal:"#42d9ad",blue:"#5ca9ff",amber:"#f7bb59",red:"#ef7180",muted:"#8299b5"};
const state={year:"All",city:"All",fleet:"All"};
const pageMeta={executive:["Executive Summary","Network health, unit economics, and delivery volume"],riders:["Rider Analytics","Productivity, utilization, and rider performance"],fleet:["1P vs 3P Performance","Operating-model efficiency and cost comparison"],cost:["Cost Control","Payout reconciliation and anomaly investigation"]};
const sum=(a,k)=>a.reduce((t,x)=>t+(+x[k]||0),0);
function filteredSummary(ignoreFleet=false){return DATA.summary.filter(x=>(state.year==="All"||x.year===state.year)&&(state.city==="All"||x.city===state.city)&&(ignoreFleet||state.fleet==="All"||x.employment_type===state.fleet))}
function filteredRiders(ignoreFleet=false){return DATA.riders.filter(x=>(state.year==="All"||x.year===state.year)&&(state.city==="All"||x.city===state.city)&&(ignoreFleet||state.fleet==="All"||x.employment_type===state.fleet))}
function filteredAnomalies(){return DATA.anomalies.filter(x=>(state.year==="All"||x.order_date.startsWith(state.year))&&(state.city==="All"||x.city===state.city)&&(state.fleet==="All"||x.employment_type===state.fleet))}
function aggregate(rows){const orders=sum(rows,"orders"),cost=sum(rows,"cost"),revenue=sum(rows,"revenue"),distance=sum(rows,"distance"),minutes=sum(rows,"minutes"),anomalies=sum(rows,"anomalies");return{orders,cost,revenue,distance,minutes,anomalies,profit:sum(rows,"profit"),expected:sum(rows,"expected_payout"),actual:sum(rows,"actual_payout"),variance:sum(rows,"variance"),cpd:cost/orders||0,avgDistance:distance/orders||0,margin:(revenue-cost)/revenue*100||0}}
function card(label,value,sub,accent="teal"){return `<div class="card" style="--accent:var(--${accent})"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`}
function group(rows,key){const m={};rows.forEach(x=>{const k=x[key];if(!m[k])m[k]=[];m[k].push(x)});return m}
function tooltip(el,label,value){el.onmousemove=e=>{const t=$("tooltip");t.style.display="block";t.style.left=(e.clientX+14)+"px";t.style.top=(e.clientY+14)+"px";t.innerHTML=`<b>${label}</b><br>${value}`};el.onmouseleave=()=>{$("tooltip").style.display="none"}}
function lineChart(id,series,opts={}){const root=$(id);if(!series.length||!series[0].values.length){root.innerHTML='<div class="empty">No data for current filters</div>';return}const W=700,H=245,p={l:48,r:18,t:15,b:35};const vals=series.flatMap(s=>s.values.map(x=>x.value));let min=opts.zero?0:Math.min(...vals),max=Math.max(...vals);if(min===max){min*=.9;max*=1.1}const gap=(max-min)*.12;min=opts.zero?0:min-gap;max+=gap;const labels=series[0].values.map(x=>x.label),x=i=>p.l+i*(W-p.l-p.r)/Math.max(labels.length-1,1),y=v=>p.t+(max-v)/(max-min)*(H-p.t-p.b);let svg=`<svg viewBox="0 0 ${W} ${H}">`;for(let i=0;i<5;i++){const yy=p.t+i*(H-p.t-p.b)/4,val=max-i*(max-min)/4;svg+=`<line class="gridline" x1="${p.l}" x2="${W-p.r}" y1="${yy}" y2="${yy}"/><text class="chart-label" x="${p.l-7}" y="${yy+3}" text-anchor="end">${opts.money?money(val):compact(val)}</text>`}labels.forEach((l,i)=>{if(i%Math.ceil(labels.length/8)===0)svg+=`<text class="chart-label" x="${x(i)}" y="${H-10}" text-anchor="middle">${l.slice(2)}</text>`});series.forEach((s,si)=>{const pts=s.values.map((v,i)=>`${x(i)},${y(v.value)}`).join(" ");svg+=`<polyline fill="none" stroke="${s.color}" stroke-width="3" points="${pts}"/>`;s.values.forEach((v,i)=>svg+=`<circle class="point" data-si="${si}" data-i="${i}" cx="${x(i)}" cy="${y(v.value)}" r="4" fill="${s.color}"/>`)});svg+="</svg>";root.innerHTML=svg;root.querySelectorAll(".point").forEach(el=>{const s=series[+el.dataset.si],v=s.values[+el.dataset.i];tooltip(el,`${s.name} · ${v.label}`,opts.money?money(v.value):Number(v.value).toLocaleString("en-IN",{maximumFractionDigits:2}))})}
function barRows(id,items,valueLabel=compact,color="linear-gradient(90deg,var(--blue),var(--teal))"){const root=$(id),max=Math.max(...items.map(x=>x.value),1);root.innerHTML=items.map(x=>`<div class="barrow"><span>${x.label}</span><div class="bartrack"><div class="barfill" style="width:${100*x.value/max}%;background:${color}"></div></div><b>${valueLabel(x.value)}</b></div>`).join("")||'<div class="empty">No data</div>'}
function columnChart(id,items,color=colors.blue){const root=$(id),W=700,H=245,p={l:42,r:15,t:15,b:40},max=Math.max(...items.map(x=>x.value),1),bw=(W-p.l-p.r)/items.length*.58;let svg=`<svg viewBox="0 0 ${W} ${H}">`;for(let i=0;i<5;i++){const yy=p.t+i*(H-p.t-p.b)/4;svg+=`<line class="gridline" x1="${p.l}" x2="${W-p.r}" y1="${yy}" y2="${yy}"/><text class="chart-label" x="${p.l-6}" y="${yy+3}" text-anchor="end">${compact(max-i*max/4)}</text>`}items.forEach((v,i)=>{const slot=(W-p.l-p.r)/items.length,bh=v.value/max*(H-p.t-p.b),xx=p.l+i*slot+(slot-bw)/2,yy=H-p.b-bh;svg+=`<rect class="col" data-i="${i}" x="${xx}" y="${yy}" width="${bw}" height="${bh}" rx="4" fill="${color}"/><text class="chart-label" x="${xx+bw/2}" y="${H-12}" text-anchor="middle">${v.label}</text>`});svg+="</svg>";root.innerHTML=svg;root.querySelectorAll(".col").forEach(el=>{const v=items[+el.dataset.i];tooltip(el,v.label,v.value.toLocaleString("en-IN"))})}
function table(id,headers,rows){$(id).innerHTML=`<thead><tr>${headers.map(h=>`<th>${h[0]}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${headers.map(h=>`<td>${h[2]?h[2](r[h[1]],r):r[h[1]]}</td>`).join("")}</tr>`).join("")}</tbody>`}
function monthly(rows,metric,calc){return Object.entries(group(rows,"month")).sort().map(([label,r])=>({label,value:calc?calc(r):sum(r,metric)}))}
function renderExecutive(){const rows=filteredSummary(),a=aggregate(rows),riderCount=new Set(filteredRiders().map(x=>x.rider_id)).size,prodRows=filteredRiders(),productivity=sum(prodRows,"orders")/sum(prodRows,"shift_hours")||0;$("execCards").innerHTML=card("Delivered Orders",a.orders.toLocaleString("en-IN"),"Completed deliveries","teal")+card("Active Riders",riderCount.toLocaleString("en-IN"),"Distinct riders","blue")+card("Average CPD",money(a.cpd),"Cost per delivery","amber")+card("Productivity",decimal(productivity,2)+"/hr","Orders per shift hour","teal")+card("Profit Margin",decimal(a.margin,1)+"%","Allocated operating margin",a.margin>=0?"blue":"red");lineChart("cpdChart",[{name:"CPD",color:colors.blue,values:monthly(rows,"cost",r=>sum(r,"cost")/sum(r,"orders"))}],{money:true});const cities=Object.entries(group(rows,"city")).map(([label,r])=>({label,value:sum(r,"orders")})).sort((a,b)=>b.value-a.value);barRows("cityBars",cities);columnChart("ordersChart",monthly(rows,"orders").map(x=>({label:x.label.slice(5),value:x.value})),colors.blue);lineChart("financeChart",[{name:"Revenue",color:colors.teal,values:monthly(rows,"revenue")},{name:"Cost",color:colors.amber,values:monthly(rows,"cost")}],{money:true,zero:true})}
function riderAgg(){const m={};filteredRiders().forEach(x=>{if(!m[x.rider_id])m[x.rider_id]={...x,orders:0,shift_hours:0,active_hours:0,cost:0,revenue:0};["orders","shift_hours","active_hours","cost","revenue"].forEach(k=>m[x.rider_id][k]+=+x[k])});return Object.values(m).map(x=>({...x,productivity:x.orders/x.shift_hours,utilization:x.active_hours/x.shift_hours}))}
function renderRiders(){const riders=riderAgg(),totalOrders=sum(riders,"orders"),avgProd=totalOrders/sum(riders,"shift_hours")||0,avgUtil=sum(riders,"active_hours")/sum(riders,"shift_hours")*100||0,top=[...riders].filter(x=>x.orders>=20).sort((a,b)=>b.productivity-a.productivity),bottom=[...top].reverse();$("riderCards").innerHTML=card("Active Riders",riders.length.toLocaleString("en-IN"),"Within current filters","blue")+card("Delivered Orders",totalOrders.toLocaleString("en-IN"),"Rider-day completed orders","teal")+card("Avg Productivity",decimal(avgProd,3),"Orders per shift hour","teal")+card("Avg Utilization",decimal(avgUtil,1)+"%","Active delivery time","amber")+card("Avg Orders / Rider",decimal(totalOrders/riders.length,1),"Completed orders","blue");const heads=[["Rider","rider_name"],["City","city"],["Vehicle","vehicle_type"],["Orders","orders",v=>v.toLocaleString("en-IN")],["Productivity","productivity",v=>`<span class="badge good">${decimal(v,3)}</span>`]];table("topRiders",heads,top.slice(0,10));table("bottomRiders",heads,bottom.slice(0,10).map(x=>({...x,productivity:x.productivity})));const bands=[["< 0.10",0,.1],["0.10–0.15",.1,.15],["0.15–0.20",.15,.2],["0.20+",.2,99]].map(([label,l,h])=>({label,value:riders.filter(x=>x.productivity>=l&&x.productivity<h).length}));columnChart("productivityChart",bands,colors.teal);const vehicles=Object.entries(group(riders,"vehicle_type")).map(([label,r])=>({label,value:r.length})).sort((a,b)=>b.value-a.value);barRows("vehicleBars",vehicles,x=>x, "linear-gradient(90deg,var(--amber),var(--red))")}
function fleetStats(type){const rows=filteredSummary(true).filter(x=>x.employment_type===type),a=aggregate(rows),rr=filteredRiders(true).filter(x=>x.employment_type===type),riderMap={};rr.forEach(x=>{if(!riderMap[x.rider_id])riderMap[x.rider_id]={orders:0,shift:0,active:0};riderMap[x.rider_id].orders+=+x.orders;riderMap[x.rider_id].shift+=+x.shift_hours;riderMap[x.rider_id].active+=+x.active_hours});const rv=Object.values(riderMap);return{...a,riders:rv.length,productivity:sum(rv,"orders")/sum(rv,"shift")||0,utilization:sum(rv,"active")/sum(rv,"shift")*100||0}}
function renderFleet(){const one=fleetStats("1P"),three=fleetStats("3P"),total=one.orders+three.orders;$("fleetCards").innerHTML=card("Total Deliveries",total.toLocaleString("en-IN"),"Across both models","teal")+card("1P Order Share",decimal(one.orders/total*100,1)+"%","First-party fleet","blue")+card("3P Order Share",decimal(three.orders/total*100,1)+"%","Partner fleet","amber")+card("CPD Difference",money(Math.abs(one.cpd-three.cpd)),one.cpd>three.cpd?"1P is higher":"3P is higher","red")+card("Margin Difference",decimal(Math.abs(one.margin-three.margin),1)+" pts","Absolute margin gap","teal");const box=(name,s,color)=>`<div class="compare-box"><div class="compare-head"><b style="color:${color}">${name}</b><span class="badge">${s.riders} riders</span></div><div class="metric-row"><span>Delivered Orders</span><b>${s.orders.toLocaleString("en-IN")}</b></div><div class="metric-row"><span>Average CPD</span><b>${money(s.cpd)}</b></div><div class="metric-row"><span>Productivity</span><b>${decimal(s.productivity,3)}/hr</b></div><div class="metric-row"><span>Utilization</span><b>${decimal(s.utilization,1)}%</b></div><div class="metric-row"><span>Profit Margin</span><b>${decimal(s.margin,1)}%</b></div></div>`;$("fleetCompare").innerHTML=box("1P Fleet",one,colors.teal)+box("3P Fleet",three,colors.amber);const base=filteredSummary(true),months=[...new Set(base.map(x=>x.month))].sort(),series=["1P","3P"].map((type,i)=>({name:type,color:i?colors.amber:colors.teal,values:months.map(label=>{const r=base.filter(x=>x.month===label&&x.employment_type===type);return{label,value:sum(r,"cost")/sum(r,"orders")||0}})}));lineChart("fleetCpdChart",series,{money:true});const p1=one.orders/total*100||0;$("fleetDonut").innerHTML=`<div style="position:relative"><div class="donut" style="background:conic-gradient(var(--teal) 0 ${p1}%,var(--amber) ${p1}% 100%)"></div><div class="donut-center" style="left:50%;top:50%;transform:translate(-50%,-50%)"><b>${compact(total)}</b><span>DELIVERIES</span></div></div><div><p><i class="dot" style="background:var(--teal)"></i><b>1P</b><br><span style="color:var(--muted)">${one.orders.toLocaleString("en-IN")} · ${decimal(p1,1)}%</span></p><p><i class="dot" style="background:var(--amber)"></i><b>3P</b><br><span style="color:var(--muted)">${three.orders.toLocaleString("en-IN")} · ${decimal(100-p1,1)}%</span></p></div>`}
function renderCost(){const rows=filteredSummary(),a=aggregate(rows),an=filteredAnomalies(),rate=a.anomalies/a.orders*100||0;$("costCards").innerHTML=card("Expected Payout",money(a.expected),"Approved rate card","blue")+card("Actual Payout",money(a.actual),"Paid or invoiced","amber")+card("Payout Variance",money(a.variance),decimal(a.variance/a.expected*100,2)+"% of expected","red")+card("Cost Anomalies",a.anomalies.toLocaleString("en-IN"),decimal(rate,2)+"% anomaly rate","amber")+card("Profit Impact",money(sum(an,"delivery_cost")-sum(an,"expected_payout")),"Excess cost in anomaly queue","red");lineChart("varianceChart",[{name:"Variance",color:colors.red,values:monthly(rows,"variance")}],{money:true});const cities=Object.entries(group(an,"city")).map(([label,r])=>({label,value:r.length})).sort((a,b)=>b.value-a.value);barRows("anomalyBars",cities,x=>x,"linear-gradient(90deg,var(--amber),var(--red))");table("anomalyTable",[["Order","order_id"],["Date","order_date"],["City","city"],["Fleet","employment_type",v=>`<span class="badge">${v}</span>`],["Rider","rider_id"],["Distance","delivery_distance_km",v=>decimal(v,2)+" km"],["Expected","expected_payout",money],["Actual","actual_payout",money],["Variance","payout_variance",v=>`<span class="badge bad">${money(v)}</span>`],["Cost","delivery_cost",money]],an.slice(0,100))}
function render(){renderExecutive();renderRiders();renderFleet();renderCost()}
DATA.summary.forEach(x=>{x.year=String(x.year)});[...new Set(DATA.summary.map(x=>x.city))].sort().forEach(c=>$("cityFilter").insertAdjacentHTML("beforeend",`<option>${c}</option>`));
document.querySelectorAll(".nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll(".nav button,.page").forEach(x=>x.classList.remove("active"));b.classList.add("active");$(b.dataset.page).classList.add("active");$("pageTitle").textContent=pageMeta[b.dataset.page][0];$("pageSubtitle").textContent=pageMeta[b.dataset.page][1]});
[["yearFilter","year"],["cityFilter","city"],["fleetFilter","fleet"]].forEach(([id,key])=>$(id).onchange=e=>{state[key]=e.target.value;render()});
render();
</script>
</body>
</html>
"""


def main() -> None:
    data = json.dumps(load_data(), separators=(",", ":"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(HTML.replace("__DATA__", data), encoding="utf-8")
    print(f"Created standalone dashboard: {OUTPUT}")


if __name__ == "__main__":
    main()
