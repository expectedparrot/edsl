import{p as B}from"./chunk-353BL4L5-BksYHD-a.js";import{_ as l,s as v,g as P,q as W,p as z,a as F,b as S,E as w,I as E,d as T,y as D,F as A,G as R,l as x}from"./mermaid-DtZe25vs.js";import{p as Y}from"./treemap-75Q7IDZK-K8LGav4g.js";import"./index-Bcef--wg.js";import"./transform-CDNfLgV5.js";import"./timer-Bqd5yn_a.js";import"./step-BwsUM5iJ.js";import"./_baseEach-DGd582mx.js";import"./_baseUniq-3dgyUdOn.js";import"./min-T_V1UNpm.js";import"./_baseMap-BynvX5nz.js";import"./clone-BTOAhq7k.js";import"./_createAggregator-FrHfH_H0.js";var $={packet:[]},u=structuredClone($),H=R.packet,I=l(()=>{const t=w({...H,...A().packet});return t.showBits&&(t.paddingY+=10),t},"getConfig"),L=l(()=>u.packet,"getPacket"),m={pushWord:l(t=>{t.length>0&&u.packet.push(t)},"pushWord"),getPacket:L,getConfig:I,clear:l(()=>{D(),u=structuredClone($)},"clear"),setAccTitle:S,getAccTitle:F,setDiagramTitle:z,getDiagramTitle:W,getAccDescription:P,setAccDescription:v},j=l(t=>{B(t,m);let e=-1,o=[],n=1;const{bitsPerRow:i}=m.getConfig();for(let{start:a,end:r,bits:d,label:k}of t.blocks){if(a!==void 0&&r!==void 0&&r<a)throw new Error(`Packet block ${a} - ${r} is invalid. End must be greater than start.`);if(a??(a=e+1),a!==e+1)throw new Error(`Packet block ${a} - ${r??a} is not contiguous. It should start from ${e+1}.`);if(d===0)throw new Error(`Packet block ${a} is invalid. Cannot have a zero bit field.`);for(r??(r=a+(d??1)-1),d??(d=r-a+1),e=r,x.debug(`Packet block ${a} - ${e} with label ${k}`);o.length<=i+1&&m.getPacket().length<1e4;){const[c,p]=q({start:a,end:r,bits:d,label:k},n,i);if(o.push(c),c.end+1===n*i&&(m.pushWord(o),o=[],n++),!p)break;({start:a,end:r,bits:d,label:k}=p)}}m.pushWord(o)},"populate"),q=l((t,e,o)=>{if(t.start===void 0)throw new Error("start should have been set during first phase");if(t.end===void 0)throw new Error("end should have been set during first phase");if(t.start>t.end)throw new Error(`Block start ${t.start} is greater than block end ${t.end}.`);if(t.end+1<=e*o)return[t,void 0];const n=e*o-1,i=e*o;return[{start:t.start,end:n,label:t.label,bits:n-t.start},{start:i,end:t.end,label:t.label,bits:t.end-i}]},"getNextFittingBlock"),G={parse:l(async t=>{const e=await Y("packet",t);x.debug(e),j(e)},"parse")},M=l((t,e,o,n)=>{const i=n.db,a=i.getConfig(),{rowHeight:r,paddingY:d,bitWidth:k,bitsPerRow:c}=a,p=i.getPacket(),s=i.getDiagramTitle(),h=r+d,b=h*(p.length+1)-(s?0:r),g=k*c+2,f=E(e);f.attr("viewbox",`0 0 ${g} ${b}`),T(f,b,g,a.useMaxWidth);for(const[y,C]of p.entries())N(f,C,y,a);f.append("text").text(s).attr("x",g/2).attr("y",b-h/2).attr("dominant-baseline","middle").attr("text-anchor","middle").attr("class","packetTitle")},"draw"),N=l((t,e,o,{rowHeight:n,paddingX:i,paddingY:a,bitWidth:r,bitsPerRow:d,showBits:k})=>{const c=t.append("g"),p=o*(n+a)+a;for(const s of e){const h=s.start%d*r+1,b=(s.end-s.start+1)*r-i;if(c.append("rect").attr("x",h).attr("y",p).attr("width",b).attr("height",n).attr("class","packetBlock"),c.append("text").attr("x",h+b/2).attr("y",p+n/2).attr("class","packetLabel").attr("dominant-baseline","middle").attr("text-anchor","middle").text(s.label),!k)continue;const g=s.end===s.start,f=p-2;c.append("text").attr("x",h+(g?b/2:0)).attr("y",f).attr("class","packetByte start").attr("dominant-baseline","auto").attr("text-anchor",g?"middle":"start").text(s.start),g||c.append("text").attr("x",h+b).attr("y",f).attr("class","packetByte end").attr("dominant-baseline","auto").attr("text-anchor","end").text(s.end)}},"drawWord"),X={byteFontSize:"10px",startByteColor:"black",endByteColor:"black",labelColor:"black",labelFontSize:"12px",titleColor:"black",titleFontSize:"14px",blockStrokeColor:"black",blockStrokeWidth:"1",blockFillColor:"#efefef"},_={parser:G,db:m,renderer:{draw:M},styles:l(({packet:t}={})=>{const e=w(X,t);return`
	.packetByte {
		font-size: ${e.byteFontSize};
	}
	.packetByte.start {
		fill: ${e.startByteColor};
	}
	.packetByte.end {
		fill: ${e.endByteColor};
	}
	.packetLabel {
		fill: ${e.labelColor};
		font-size: ${e.labelFontSize};
	}
	.packetTitle {
		fill: ${e.titleColor};
		font-size: ${e.titleFontSize};
	}
	.packetBlock {
		stroke: ${e.blockStrokeColor};
		stroke-width: ${e.blockStrokeWidth};
		fill: ${e.blockFillColor};
	}
	`},"styles")};export{_ as diagram};
