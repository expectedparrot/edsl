import{p as B}from"./chunk-353BL4L5-BksYHD-a.js";import{_ as c,g as E,s as N,a as P,b as V,q,p as G,l as O,c as I,E as _,I as H,O as J,d as K,y as Q,G as U}from"./mermaid-DtZe25vs.js";import{p as X}from"./treemap-75Q7IDZK-K8LGav4g.js";import"./transform-CDNfLgV5.js";import{d as W}from"./arc-ZB5pDULS.js";import{o as Y}from"./ordinal-DDUp3AbE.js";import{a as y,t as z,n as Z}from"./step-BwsUM5iJ.js";import"./index-Bcef--wg.js";import"./_baseEach-DGd582mx.js";import"./_baseUniq-3dgyUdOn.js";import"./min-T_V1UNpm.js";import"./_baseMap-BynvX5nz.js";import"./clone-BTOAhq7k.js";import"./_createAggregator-FrHfH_H0.js";import"./timer-Bqd5yn_a.js";import"./init-DLRA0X12.js";function tt(t,a){return a<t?-1:a>t?1:a>=t?0:NaN}function et(t){return t}var at=U.pie,R={sections:new Map,showData:!1},M=R.sections,F=R.showData,nt=structuredClone(at),L={getConfig:c(()=>structuredClone(nt),"getConfig"),clear:c(()=>{M=new Map,F=R.showData,Q()},"clear"),setDiagramTitle:G,getDiagramTitle:q,setAccTitle:V,getAccTitle:P,setAccDescription:N,getAccDescription:E,addSection:c(({label:t,value:a})=>{M.has(t)||(M.set(t,a),O.debug(`added new section: ${t}, with value: ${a}`))},"addSection"),getSections:c(()=>M,"getSections"),setShowData:c(t=>{F=t},"setShowData"),getShowData:c(()=>F,"getShowData")},rt=c((t,a)=>{B(t,a),a.setShowData(t.showData),t.sections.map(a.addSection)},"populateDb"),it={parse:c(async t=>{const a=await X("pie",t);O.debug(a),rt(a,L)},"parse")},ot=c(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),lt=c(t=>{const a=[...t.entries()].map(l=>({label:l[0],value:l[1]})).sort((l,d)=>d.value-l.value);return function(){var l=et,d=tt,u=null,w=y(0),S=y(z),$=y(0);function n(e){var r,s,i,A,m,p=(e=Z(e)).length,v=0,T=new Array(p),g=new Array(p),f=+w.apply(this,arguments),C=Math.min(z,Math.max(-z,S.apply(this,arguments)-f)),h=Math.min(Math.abs(C)/p,$.apply(this,arguments)),b=h*(C<0?-1:1);for(r=0;r<p;++r)(m=g[T[r]=r]=+l(e[r],r,e))>0&&(v+=m);for(d!=null?T.sort(function(x,D){return d(g[x],g[D])}):u!=null&&T.sort(function(x,D){return u(e[x],e[D])}),r=0,i=v?(C-p*b)/v:0;r<p;++r,f=A)s=T[r],A=f+((m=g[s])>0?m*i:0)+b,g[s]={data:e[s],index:r,value:m,startAngle:f,endAngle:A,padAngle:h};return g}return n.value=function(e){return arguments.length?(l=typeof e=="function"?e:y(+e),n):l},n.sortValues=function(e){return arguments.length?(d=e,u=null,n):d},n.sort=function(e){return arguments.length?(u=e,d=null,n):u},n.startAngle=function(e){return arguments.length?(w=typeof e=="function"?e:y(+e),n):w},n.endAngle=function(e){return arguments.length?(S=typeof e=="function"?e:y(+e),n):S},n.padAngle=function(e){return arguments.length?($=typeof e=="function"?e:y(+e),n):$},n}().value(l=>l.value)(a)},"createPieArcs"),st={parser:it,db:L,renderer:{draw:c((t,a,l,d)=>{O.debug(`rendering pie chart
`+t);const u=d.db,w=I(),S=_(u.getConfig(),w.pie),$=18,n=450,e=n,r=H(a),s=r.append("g");s.attr("transform","translate(225,225)");const{themeVariables:i}=w;let[A]=J(i.pieOuterStrokeWidth);A??(A=2);const m=S.textPosition,p=Math.min(e,n)/2-40,v=W().innerRadius(0).outerRadius(p),T=W().innerRadius(p*m).outerRadius(p*m);s.append("circle").attr("cx",0).attr("cy",0).attr("r",p+A/2).attr("class","pieOuterCircle");const g=u.getSections(),f=lt(g),C=[i.pie1,i.pie2,i.pie3,i.pie4,i.pie5,i.pie6,i.pie7,i.pie8,i.pie9,i.pie10,i.pie11,i.pie12],h=Y(C);s.selectAll("mySlices").data(f).enter().append("path").attr("d",v).attr("fill",o=>h(o.data.label)).attr("class","pieCircle");let b=0;g.forEach(o=>{b+=o}),s.selectAll("mySlices").data(f).enter().append("text").text(o=>(o.data.value/b*100).toFixed(0)+"%").attr("transform",o=>"translate("+T.centroid(o)+")").style("text-anchor","middle").attr("class","slice"),s.append("text").text(u.getDiagramTitle()).attr("x",0).attr("y",-200).attr("class","pieTitleText");const x=s.selectAll(".legend").data(h.domain()).enter().append("g").attr("class","legend").attr("transform",(o,k)=>"translate(216,"+(22*k-22*h.domain().length/2)+")");x.append("rect").attr("width",$).attr("height",$).style("fill",h).style("stroke",h),x.data(f).append("text").attr("x",22).attr("y",14).text(o=>{const{label:k,value:j}=o.data;return u.getShowData()?`${k} [${j}]`:k});const D=512+Math.max(...x.selectAll("text").nodes().map(o=>(o==null?void 0:o.getBoundingClientRect().width)??0));r.attr("viewBox",`0 0 ${D} 450`),K(r,n,D,S.useMaxWidth)},"draw")},styles:ot};export{st as diagram};
