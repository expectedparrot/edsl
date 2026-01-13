import{_ as d,g as le,s as de,q as ue,p as he,a as fe,b as me,c as ot,d as ye,ap as V,l as mt,j as ke,i as pe,y as ge,u as be}from"./mermaid-DtZe25vs.js";import{z as gt,bV as Wt,bN as Ot,bM as ve,cr as xe,cs as Te,ct as we,cu as _e,cv as De,cw as $e,bL as Pt,bK as zt,bJ as Bt,bz as Ht,bI as Nt}from"./index-Bcef--wg.js";import{s as bt}from"./transform-CDNfLgV5.js";import{t as Ce,m as Se,a as Me,i as Ee}from"./time-CGVH8-aM.js";import{l as Ae}from"./linear-BqvUFknI.js";import"./step-BwsUM5iJ.js";import"./timer-Bqd5yn_a.js";import"./init-DLRA0X12.js";function Le(t){return t}var Gt=1e-6;function Ie(t){return"translate("+t+",0)"}function Ye(t){return"translate(0,"+t+")"}function Fe(t){return n=>+t(n)}function We(t,n){return n=Math.max(0,t.bandwidth()-2*n)/2,t.round()&&(n=Math.round(n)),s=>+t(s)+n}function Oe(){return!this.__axis}function jt(t,n){var s=[],r=null,i=null,c=6,h=6,A=3,x=typeof window<"u"&&window.devicePixelRatio>1?0:.5,$=t===1||t===4?-1:1,L=t===4||t===2?"x":"y",W=t===1||t===3?Ie:Ye;function S(D){var p=r??(n.ticks?n.ticks.apply(n,s):n.domain()),y=i??(n.tickFormat?n.tickFormat.apply(n,s):Le),M=Math.max(c,0)+A,E=n.range(),P=+E[0]+x,z=+E[E.length-1]+x,j=(n.bandwidth?We:Fe)(n.copy(),x),B=D.selection?D.selection():D,O=B.selectAll(".domain").data([null]),Y=B.selectAll(".tick").data(p,n).order(),k=Y.exit(),w=Y.enter().append("g").attr("class","tick"),b=Y.select("line"),g=Y.select("text");O=O.merge(O.enter().insert("path",".tick").attr("class","domain").attr("stroke","currentColor")),Y=Y.merge(w),b=b.merge(w.append("line").attr("stroke","currentColor").attr(L+"2",$*c)),g=g.merge(w.append("text").attr("fill","currentColor").attr(L,$*M).attr("dy",t===1?"0em":t===3?"0.71em":"0.32em")),D!==B&&(O=O.transition(D),Y=Y.transition(D),b=b.transition(D),g=g.transition(D),k=k.transition(D).attr("opacity",Gt).attr("transform",function(f){return isFinite(f=j(f))?W(f+x):this.getAttribute("transform")}),w.attr("opacity",Gt).attr("transform",function(f){var o=this.parentNode.__axis;return W((o&&isFinite(o=o(f))?o:j(f))+x)})),k.remove(),O.attr("d",t===4||t===2?h?"M"+$*h+","+P+"H"+x+"V"+z+"H"+$*h:"M"+x+","+P+"V"+z:h?"M"+P+","+$*h+"V"+x+"H"+z+"V"+$*h:"M"+P+","+x+"H"+z),Y.attr("opacity",1).attr("transform",function(f){return W(j(f)+x)}),b.attr(L+"2",$*c),g.attr(L,$*M).text(y),B.filter(Oe).attr("fill","none").attr("font-size",10).attr("font-family","sans-serif").attr("text-anchor",t===2?"start":t===4?"end":"middle"),B.each(function(){this.__axis=j})}return S.scale=function(D){return arguments.length?(n=D,S):n},S.ticks=function(){return s=Array.from(arguments),S},S.tickArguments=function(D){return arguments.length?(s=D==null?[]:Array.from(D),S):s.slice()},S.tickValues=function(D){return arguments.length?(r=D==null?null:Array.from(D),S):r&&r.slice()},S.tickFormat=function(D){return arguments.length?(i=D,S):i},S.tickSize=function(D){return arguments.length?(c=h=+D,S):c},S.tickSizeInner=function(D){return arguments.length?(c=+D,S):c},S.tickSizeOuter=function(D){return arguments.length?(h=+D,S):h},S.tickPadding=function(D){return arguments.length?(A=+D,S):A},S.offset=function(D){return arguments.length?(x=+D,S):x},S}var Vt,yt,Rt={exports:{}};const Pe=gt(Vt?Rt.exports:(Vt=1,Rt.exports=(yt="day",function(t,n,s){var r=function(h){return h.add(4-h.isoWeekday(),yt)},i=n.prototype;i.isoWeekYear=function(){return r(this).year()},i.isoWeek=function(h){if(!this.$utils().u(h))return this.add(7*(h-this.isoWeek()),yt);var A,x,$,L=r(this),W=(A=this.isoWeekYear(),$=4-(x=(this.$u?s.utc:s)().year(A).startOf("year")).isoWeekday(),x.isoWeekday()>4&&($+=7),x.add($,yt));return L.diff(W,"week")+1},i.isoWeekday=function(h){return this.$utils().u(h)?this.day()||7:this.day(this.day()%7?h:h-7)};var c=i.startOf;i.startOf=function(h,A){var x=this.$utils(),$=!!x.u(A)||A;return x.p(h)==="isoweek"?$?this.date(this.date()-(this.isoWeekday()-1)).startOf("day"):this.date(this.date()-1-(this.isoWeekday()-1)+7).endOf("day"):c.bind(this)(h,A)}})));var Zt,Ut={exports:{}},ze=(Zt||(Zt=1,Ut.exports=function(){var t={LTS:"h:mm:ss A",LT:"h:mm A",L:"MM/DD/YYYY",LL:"MMMM D, YYYY",LLL:"MMMM D, YYYY h:mm A",LLLL:"dddd, MMMM D, YYYY h:mm A"},n=/(\[[^[]*\])|([-_:/.,()\s]+)|(A|a|Q|YYYY|YY?|ww?|MM?M?M?|Do|DD?|hh?|HH?|mm?|ss?|S{1,3}|z|ZZ?)/g,s=/\d/,r=/\d\d/,i=/\d\d?/,c=/\d*[^-_:/,()\s\d]+/,h={},A=function(p){return(p=+p)+(p>68?1900:2e3)},x=function(p){return function(y){this[p]=+y}},$=[/[+-]\d\d:?(\d\d)?|Z/,function(p){(this.zone||(this.zone={})).offset=function(y){if(!y||y==="Z")return 0;var M=y.match(/([+-]|\d\d)/g),E=60*M[1]+(+M[2]||0);return E===0?0:M[0]==="+"?-E:E}(p)}],L=function(p){var y=h[p];return y&&(y.indexOf?y:y.s.concat(y.f))},W=function(p,y){var M,E=h.meridiem;if(E){for(var P=1;P<=24;P+=1)if(p.indexOf(E(P,0,y))>-1){M=P>12;break}}else M=p===(y?"pm":"PM");return M},S={A:[c,function(p){this.afternoon=W(p,!1)}],a:[c,function(p){this.afternoon=W(p,!0)}],Q:[s,function(p){this.month=3*(p-1)+1}],S:[s,function(p){this.milliseconds=100*+p}],SS:[r,function(p){this.milliseconds=10*+p}],SSS:[/\d{3}/,function(p){this.milliseconds=+p}],s:[i,x("seconds")],ss:[i,x("seconds")],m:[i,x("minutes")],mm:[i,x("minutes")],H:[i,x("hours")],h:[i,x("hours")],HH:[i,x("hours")],hh:[i,x("hours")],D:[i,x("day")],DD:[r,x("day")],Do:[c,function(p){var y=h.ordinal,M=p.match(/\d+/);if(this.day=M[0],y)for(var E=1;E<=31;E+=1)y(E).replace(/\[|\]/g,"")===p&&(this.day=E)}],w:[i,x("week")],ww:[r,x("week")],M:[i,x("month")],MM:[r,x("month")],MMM:[c,function(p){var y=L("months"),M=(L("monthsShort")||y.map(function(E){return E.slice(0,3)})).indexOf(p)+1;if(M<1)throw new Error;this.month=M%12||M}],MMMM:[c,function(p){var y=L("months").indexOf(p)+1;if(y<1)throw new Error;this.month=y%12||y}],Y:[/[+-]?\d+/,x("year")],YY:[r,function(p){this.year=A(p)}],YYYY:[/\d{4}/,x("year")],Z:$,ZZ:$};function D(p){var y,M;y=p,M=h&&h.formats;for(var E=(p=y.replace(/(\[[^\]]+])|(LTS?|l{1,4}|L{1,4})/g,function(k,w,b){var g=b&&b.toUpperCase();return w||M[b]||t[b]||M[g].replace(/(\[[^\]]+])|(MMMM|MM|DD|dddd)/g,function(f,o,m){return o||m.slice(1)})})).match(n),P=E.length,z=0;z<P;z+=1){var j=E[z],B=S[j],O=B&&B[0],Y=B&&B[1];E[z]=Y?{regex:O,parser:Y}:j.replace(/^\[|\]$/g,"")}return function(k){for(var w={},b=0,g=0;b<P;b+=1){var f=E[b];if(typeof f=="string")g+=f.length;else{var o=f.regex,m=f.parser,u=k.slice(g),l=o.exec(u)[0];m.call(w,l),k=k.replace(l,"")}}return function(T){var e=T.afternoon;if(e!==void 0){var v=T.hours;e?v<12&&(T.hours+=12):v===12&&(T.hours=0),delete T.afternoon}}(w),w}}return function(p,y,M){M.p.customParseFormat=!0,p&&p.parseTwoDigitYear&&(A=p.parseTwoDigitYear);var E=y.prototype,P=E.parse;E.parse=function(z){var j=z.date,B=z.utc,O=z.args;this.$u=B;var Y=O[1];if(typeof Y=="string"){var k=O[2]===!0,w=O[3]===!0,b=k||w,g=O[2];w&&(g=O[2]),h=this.$locale(),!k&&g&&(h=M.Ls[g]),this.$d=function(u,l,T,e){try{if(["x","X"].indexOf(l)>-1)return new Date((l==="X"?1e3:1)*u);var v=D(l)(u),a=v.year,_=v.month,I=v.day,F=v.hours,C=v.minutes,U=v.seconds,tt=v.milliseconds,rt=v.zone,ft=v.week,st=new Date,N=I||(a||_?1:st.getDate()),q=a||st.getFullYear(),G=0;a&&!_||(G=_>0?_-1:st.getMonth());var et,X=F||0,R=C||0,at=U||0,J=tt||0;return rt?new Date(Date.UTC(q,G,N,X,R,at,J+60*rt.offset*1e3)):T?new Date(Date.UTC(q,G,N,X,R,at,J)):(et=new Date(q,G,N,X,R,at,J),ft&&(et=e(et).week(ft).toDate()),et)}catch{return new Date("")}}(j,Y,B,M),this.init(),g&&g!==!0&&(this.$L=this.locale(g).$L),b&&j!=this.format(Y)&&(this.$d=new Date("")),h={}}else if(Y instanceof Array)for(var f=Y.length,o=1;o<=f;o+=1){O[1]=Y[o-1];var m=M.apply(this,O);if(m.isValid()){this.$d=m.$d,this.$L=m.$L,this.init();break}o===f&&(this.$d=new Date(""))}else P.call(this,z)}}}()),Ut.exports);const Be=gt(ze);var qt,Qt={exports:{}},He=(qt||(qt=1,Qt.exports=function(t,n){var s=n.prototype,r=s.format;s.format=function(i){var c=this,h=this.$locale();if(!this.isValid())return r.bind(this)(i);var A=this.$utils(),x=(i||"YYYY-MM-DDTHH:mm:ssZ").replace(/\[([^\]]+)]|Q|wo|ww|w|WW|W|zzz|z|gggg|GGGG|Do|X|x|k{1,2}|S/g,function($){switch($){case"Q":return Math.ceil((c.$M+1)/3);case"Do":return h.ordinal(c.$D);case"gggg":return c.weekYear();case"GGGG":return c.isoWeekYear();case"wo":return h.ordinal(c.week(),"W");case"w":case"ww":return A.s(c.week(),$==="w"?1:2,"0");case"W":case"WW":return A.s(c.isoWeek(),$==="W"?1:2,"0");case"k":case"kk":return A.s(String(c.$H===0?24:c.$H),$==="k"?1:2,"0");case"X":return Math.floor(c.$d.getTime()/1e3);case"x":return c.$d.getTime();case"z":return"["+c.offsetName()+"]";case"zzz":return"["+c.offsetName("long")+"]";default:return $}});return r.bind(this)(x)}}),Qt.exports);const Ne=gt(He);var vt=function(){var t=d(function(o,m,u,l){for(u=u||{},l=o.length;l--;u[o[l]]=m);return u},"o"),n=[6,8,10,12,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29,30,31,33,35,36,38,40],s=[1,26],r=[1,27],i=[1,28],c=[1,29],h=[1,30],A=[1,31],x=[1,32],$=[1,33],L=[1,34],W=[1,9],S=[1,10],D=[1,11],p=[1,12],y=[1,13],M=[1,14],E=[1,15],P=[1,16],z=[1,19],j=[1,20],B=[1,21],O=[1,22],Y=[1,23],k=[1,25],w=[1,35],b={trace:d(function(){},"trace"),yy:{},symbols_:{error:2,start:3,gantt:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NL:10,weekday:11,weekday_monday:12,weekday_tuesday:13,weekday_wednesday:14,weekday_thursday:15,weekday_friday:16,weekday_saturday:17,weekday_sunday:18,weekend:19,weekend_friday:20,weekend_saturday:21,dateFormat:22,inclusiveEndDates:23,topAxis:24,axisFormat:25,tickInterval:26,excludes:27,includes:28,todayMarker:29,title:30,acc_title:31,acc_title_value:32,acc_descr:33,acc_descr_value:34,acc_descr_multiline_value:35,section:36,clickStatement:37,taskTxt:38,taskData:39,click:40,callbackname:41,callbackargs:42,href:43,clickStatementDebug:44,$accept:0,$end:1},terminals_:{2:"error",4:"gantt",6:"EOF",8:"SPACE",10:"NL",12:"weekday_monday",13:"weekday_tuesday",14:"weekday_wednesday",15:"weekday_thursday",16:"weekday_friday",17:"weekday_saturday",18:"weekday_sunday",20:"weekend_friday",21:"weekend_saturday",22:"dateFormat",23:"inclusiveEndDates",24:"topAxis",25:"axisFormat",26:"tickInterval",27:"excludes",28:"includes",29:"todayMarker",30:"title",31:"acc_title",32:"acc_title_value",33:"acc_descr",34:"acc_descr_value",35:"acc_descr_multiline_value",36:"section",38:"taskTxt",39:"taskData",40:"click",41:"callbackname",42:"callbackargs",43:"href"},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[19,1],[19,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,1],[9,2],[37,2],[37,3],[37,3],[37,4],[37,3],[37,4],[37,2],[44,2],[44,3],[44,3],[44,4],[44,3],[44,4],[44,2]],performAction:d(function(o,m,u,l,T,e,v){var a=e.length-1;switch(T){case 1:return e[a-1];case 2:case 6:case 7:this.$=[];break;case 3:e[a-1].push(e[a]),this.$=e[a-1];break;case 4:case 5:this.$=e[a];break;case 8:l.setWeekday("monday");break;case 9:l.setWeekday("tuesday");break;case 10:l.setWeekday("wednesday");break;case 11:l.setWeekday("thursday");break;case 12:l.setWeekday("friday");break;case 13:l.setWeekday("saturday");break;case 14:l.setWeekday("sunday");break;case 15:l.setWeekend("friday");break;case 16:l.setWeekend("saturday");break;case 17:l.setDateFormat(e[a].substr(11)),this.$=e[a].substr(11);break;case 18:l.enableInclusiveEndDates(),this.$=e[a].substr(18);break;case 19:l.TopAxis(),this.$=e[a].substr(8);break;case 20:l.setAxisFormat(e[a].substr(11)),this.$=e[a].substr(11);break;case 21:l.setTickInterval(e[a].substr(13)),this.$=e[a].substr(13);break;case 22:l.setExcludes(e[a].substr(9)),this.$=e[a].substr(9);break;case 23:l.setIncludes(e[a].substr(9)),this.$=e[a].substr(9);break;case 24:l.setTodayMarker(e[a].substr(12)),this.$=e[a].substr(12);break;case 27:l.setDiagramTitle(e[a].substr(6)),this.$=e[a].substr(6);break;case 28:this.$=e[a].trim(),l.setAccTitle(this.$);break;case 29:case 30:this.$=e[a].trim(),l.setAccDescription(this.$);break;case 31:l.addSection(e[a].substr(8)),this.$=e[a].substr(8);break;case 33:l.addTask(e[a-1],e[a]),this.$="task";break;case 34:this.$=e[a-1],l.setClickEvent(e[a-1],e[a],null);break;case 35:this.$=e[a-2],l.setClickEvent(e[a-2],e[a-1],e[a]);break;case 36:this.$=e[a-2],l.setClickEvent(e[a-2],e[a-1],null),l.setLink(e[a-2],e[a]);break;case 37:this.$=e[a-3],l.setClickEvent(e[a-3],e[a-2],e[a-1]),l.setLink(e[a-3],e[a]);break;case 38:this.$=e[a-2],l.setClickEvent(e[a-2],e[a],null),l.setLink(e[a-2],e[a-1]);break;case 39:this.$=e[a-3],l.setClickEvent(e[a-3],e[a-1],e[a]),l.setLink(e[a-3],e[a-2]);break;case 40:this.$=e[a-1],l.setLink(e[a-1],e[a]);break;case 41:case 47:this.$=e[a-1]+" "+e[a];break;case 42:case 43:case 45:this.$=e[a-2]+" "+e[a-1]+" "+e[a];break;case 44:case 46:this.$=e[a-3]+" "+e[a-2]+" "+e[a-1]+" "+e[a]}},"anonymous"),table:[{3:1,4:[1,2]},{1:[3]},t(n,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:17,12:s,13:r,14:i,15:c,16:h,17:A,18:x,19:18,20:$,21:L,22:W,23:S,24:D,25:p,26:y,27:M,28:E,29:P,30:z,31:j,33:B,35:O,36:Y,37:24,38:k,40:w},t(n,[2,7],{1:[2,1]}),t(n,[2,3]),{9:36,11:17,12:s,13:r,14:i,15:c,16:h,17:A,18:x,19:18,20:$,21:L,22:W,23:S,24:D,25:p,26:y,27:M,28:E,29:P,30:z,31:j,33:B,35:O,36:Y,37:24,38:k,40:w},t(n,[2,5]),t(n,[2,6]),t(n,[2,17]),t(n,[2,18]),t(n,[2,19]),t(n,[2,20]),t(n,[2,21]),t(n,[2,22]),t(n,[2,23]),t(n,[2,24]),t(n,[2,25]),t(n,[2,26]),t(n,[2,27]),{32:[1,37]},{34:[1,38]},t(n,[2,30]),t(n,[2,31]),t(n,[2,32]),{39:[1,39]},t(n,[2,8]),t(n,[2,9]),t(n,[2,10]),t(n,[2,11]),t(n,[2,12]),t(n,[2,13]),t(n,[2,14]),t(n,[2,15]),t(n,[2,16]),{41:[1,40],43:[1,41]},t(n,[2,4]),t(n,[2,28]),t(n,[2,29]),t(n,[2,33]),t(n,[2,34],{42:[1,42],43:[1,43]}),t(n,[2,40],{41:[1,44]}),t(n,[2,35],{43:[1,45]}),t(n,[2,36]),t(n,[2,38],{42:[1,46]}),t(n,[2,37]),t(n,[2,39])],defaultActions:{},parseError:d(function(o,m){if(!m.recoverable){var u=new Error(o);throw u.hash=m,u}this.trace(o)},"parseError"),parse:d(function(o){var m=this,u=[0],l=[],T=[null],e=[],v=this.table,a="",_=0,I=0,F=e.slice.call(arguments,1),C=Object.create(this.lexer),U={yy:{}};for(var tt in this.yy)Object.prototype.hasOwnProperty.call(this.yy,tt)&&(U.yy[tt]=this.yy[tt]);C.setInput(o,U.yy),U.yy.lexer=C,U.yy.parser=this,C.yylloc===void 0&&(C.yylloc={});var rt=C.yylloc;e.push(rt);var ft=C.options&&C.options.ranges;function st(){var Z;return typeof(Z=l.pop()||C.lex()||1)!="number"&&(Z instanceof Array&&(Z=(l=Z).pop()),Z=m.symbols_[Z]||Z),Z}typeof U.yy.parseError=="function"?this.parseError=U.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError,d(function(Z){u.length=u.length-2*Z,T.length=T.length-Z,e.length=e.length-Z},"popStack"),d(st,"lex");for(var N,q,G,et,X,R,at,J,nt={};;){if(q=u[u.length-1],this.defaultActions[q]?G=this.defaultActions[q]:(N==null&&(N=st()),G=v[q]&&v[q][N]),G===void 0||!G.length||!G[0]){var Ft="";for(X in J=[],v[q])this.terminals_[X]&&X>2&&J.push("'"+this.terminals_[X]+"'");Ft=C.showPosition?"Parse error on line "+(_+1)+`:
`+C.showPosition()+`
Expecting `+J.join(", ")+", got '"+(this.terminals_[N]||N)+"'":"Parse error on line "+(_+1)+": Unexpected "+(N==1?"end of input":"'"+(this.terminals_[N]||N)+"'"),this.parseError(Ft,{text:C.match,token:this.terminals_[N]||N,line:C.yylineno,loc:rt,expected:J})}if(G[0]instanceof Array&&G.length>1)throw new Error("Parse Error: multiple actions possible at state: "+q+", token: "+N);switch(G[0]){case 1:u.push(N),T.push(C.yytext),e.push(C.yylloc),u.push(G[1]),N=null,I=C.yyleng,a=C.yytext,_=C.yylineno,rt=C.yylloc;break;case 2:if(R=this.productions_[G[1]][1],nt.$=T[T.length-R],nt._$={first_line:e[e.length-(R||1)].first_line,last_line:e[e.length-1].last_line,first_column:e[e.length-(R||1)].first_column,last_column:e[e.length-1].last_column},ft&&(nt._$.range=[e[e.length-(R||1)].range[0],e[e.length-1].range[1]]),(et=this.performAction.apply(nt,[a,I,_,U.yy,G[1],T,e].concat(F)))!==void 0)return et;R&&(u=u.slice(0,-1*R*2),T=T.slice(0,-1*R),e=e.slice(0,-1*R)),u.push(this.productions_[G[1]][0]),T.push(nt.$),e.push(nt._$),at=v[u[u.length-2]][u[u.length-1]],u.push(at);break;case 3:return!0}}return!0},"parse")},g=function(){return{EOF:1,parseError:d(function(o,m){if(!this.yy.parser)throw new Error(o);this.yy.parser.parseError(o,m)},"parseError"),setInput:d(function(o,m){return this.yy=m||this.yy||{},this._input=o,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},"setInput"),input:d(function(){var o=this._input[0];return this.yytext+=o,this.yyleng++,this.offset++,this.match+=o,this.matched+=o,o.match(/(?:\r\n?|\n).*/g)?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),o},"input"),unput:d(function(o){var m=o.length,u=o.split(/(?:\r\n?|\n)/g);this._input=o+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-m),this.offset-=m;var l=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),u.length-1&&(this.yylineno-=u.length-1);var T=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:u?(u.length===l.length?this.yylloc.first_column:0)+l[l.length-u.length].length-u[0].length:this.yylloc.first_column-m},this.options.ranges&&(this.yylloc.range=[T[0],T[0]+this.yyleng-m]),this.yyleng=this.yytext.length,this},"unput"),more:d(function(){return this._more=!0,this},"more"),reject:d(function(){return this.options.backtrack_lexer?(this._backtrack=!0,this):this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"reject"),less:d(function(o){this.unput(this.match.slice(o))},"less"),pastInput:d(function(){var o=this.matched.substr(0,this.matched.length-this.match.length);return(o.length>20?"...":"")+o.substr(-20).replace(/\n/g,"")},"pastInput"),upcomingInput:d(function(){var o=this.match;return o.length<20&&(o+=this._input.substr(0,20-o.length)),(o.substr(0,20)+(o.length>20?"...":"")).replace(/\n/g,"")},"upcomingInput"),showPosition:d(function(){var o=this.pastInput(),m=new Array(o.length+1).join("-");return o+this.upcomingInput()+`
`+m+"^"},"showPosition"),test_match:d(function(o,m){var u,l,T;if(this.options.backtrack_lexer&&(T={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(T.yylloc.range=this.yylloc.range.slice(0))),(l=o[0].match(/(?:\r\n?|\n).*/g))&&(this.yylineno+=l.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:l?l[l.length-1].length-l[l.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+o[0].length},this.yytext+=o[0],this.match+=o[0],this.matches=o,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(o[0].length),this.matched+=o[0],u=this.performAction.call(this,this.yy,this,m,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),u)return u;if(this._backtrack){for(var e in T)this[e]=T[e];return!1}return!1},"test_match"),next:d(function(){if(this.done)return this.EOF;var o,m,u,l;this._input||(this.done=!0),this._more||(this.yytext="",this.match="");for(var T=this._currentRules(),e=0;e<T.length;e++)if((u=this._input.match(this.rules[T[e]]))&&(!m||u[0].length>m[0].length)){if(m=u,l=e,this.options.backtrack_lexer){if((o=this.test_match(u,T[e]))!==!1)return o;if(this._backtrack){m=!1;continue}return!1}if(!this.options.flex)break}return m?(o=this.test_match(m,T[l]))!==!1&&o:this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"next"),lex:d(function(){var o=this.next();return o||this.lex()},"lex"),begin:d(function(o){this.conditionStack.push(o)},"begin"),popState:d(function(){return this.conditionStack.length-1>0?this.conditionStack.pop():this.conditionStack[0]},"popState"),_currentRules:d(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},"_currentRules"),topState:d(function(o){return(o=this.conditionStack.length-1-Math.abs(o||0))>=0?this.conditionStack[o]:"INITIAL"},"topState"),pushState:d(function(o){this.begin(o)},"pushState"),stateStackSize:d(function(){return this.conditionStack.length},"stateStackSize"),options:{"case-insensitive":!0},performAction:d(function(o,m,u,l){switch(u){case 0:return this.begin("open_directive"),"open_directive";case 1:return this.begin("acc_title"),31;case 2:return this.popState(),"acc_title_value";case 3:return this.begin("acc_descr"),33;case 4:return this.popState(),"acc_descr_value";case 5:this.begin("acc_descr_multiline");break;case 6:case 15:case 18:case 21:case 24:this.popState();break;case 7:return"acc_descr_multiline_value";case 8:case 9:case 10:case 12:case 13:break;case 11:return 10;case 14:this.begin("href");break;case 16:return 43;case 17:this.begin("callbackname");break;case 19:this.popState(),this.begin("callbackargs");break;case 20:return 41;case 22:return 42;case 23:this.begin("click");break;case 25:return 40;case 26:return 4;case 27:return 22;case 28:return 23;case 29:return 24;case 30:return 25;case 31:return 26;case 32:return 28;case 33:return 27;case 34:return 29;case 35:return 12;case 36:return 13;case 37:return 14;case 38:return 15;case 39:return 16;case 40:return 17;case 41:return 18;case 42:return 20;case 43:return 21;case 44:return"date";case 45:return 30;case 46:return"accDescription";case 47:return 36;case 48:return 38;case 49:return 39;case 50:return":";case 51:return 6;case 52:return"INVALID"}},"anonymous"),rules:[/^(?:%%\{)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:%%(?!\{)*[^\n]*)/i,/^(?:[^\}]%%*[^\n]*)/i,/^(?:%%*[^\n]*[\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:%[^\n]*)/i,/^(?:href[\s]+["])/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:call[\s]+)/i,/^(?:\([\s]*\))/i,/^(?:\()/i,/^(?:[^(]*)/i,/^(?:\))/i,/^(?:[^)]*)/i,/^(?:click[\s]+)/i,/^(?:[\s\n])/i,/^(?:[^\s\n]*)/i,/^(?:gantt\b)/i,/^(?:dateFormat\s[^#\n;]+)/i,/^(?:inclusiveEndDates\b)/i,/^(?:topAxis\b)/i,/^(?:axisFormat\s[^#\n;]+)/i,/^(?:tickInterval\s[^#\n;]+)/i,/^(?:includes\s[^#\n;]+)/i,/^(?:excludes\s[^#\n;]+)/i,/^(?:todayMarker\s[^\n;]+)/i,/^(?:weekday\s+monday\b)/i,/^(?:weekday\s+tuesday\b)/i,/^(?:weekday\s+wednesday\b)/i,/^(?:weekday\s+thursday\b)/i,/^(?:weekday\s+friday\b)/i,/^(?:weekday\s+saturday\b)/i,/^(?:weekday\s+sunday\b)/i,/^(?:weekend\s+friday\b)/i,/^(?:weekend\s+saturday\b)/i,/^(?:\d\d\d\d-\d\d-\d\d\b)/i,/^(?:title\s[^\n]+)/i,/^(?:accDescription\s[^#\n;]+)/i,/^(?:section\s[^\n]+)/i,/^(?:[^:\n]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[6,7],inclusive:!1},acc_descr:{rules:[4],inclusive:!1},acc_title:{rules:[2],inclusive:!1},callbackargs:{rules:[21,22],inclusive:!1},callbackname:{rules:[18,19,20],inclusive:!1},href:{rules:[15,16],inclusive:!1},click:{rules:[24,25],inclusive:!1},INITIAL:{rules:[0,1,3,5,8,9,10,11,12,13,14,17,23,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52],inclusive:!0}}}}();function f(){this.yy={}}return b.lexer=g,d(f,"Parser"),f.prototype=b,b.Parser=f,new f}();vt.parser=vt;var Ge=vt;V.extend(Pe),V.extend(Be),V.extend(Ne);var xt,kt,Xt={friday:5,saturday:6},Q="",Tt="",wt=void 0,_t="",dt=[],ut=[],Dt=new Map,$t=[],Ct=[],ct="",St="",Jt=["active","done","crit","milestone","vert"],Mt=[],ht=!1,Et=!1,At="sunday",pt="saturday",Lt=0,je=d(function(){$t=[],Ct=[],ct="",Mt=[],ie=0,xt=void 0,kt=void 0,H=[],Q="",Tt="",St="",wt=void 0,_t="",dt=[],ut=[],ht=!1,Et=!1,Lt=0,Dt=new Map,ge(),At="sunday",pt="saturday"},"clear"),Ve=d(function(t){Tt=t},"setAxisFormat"),Re=d(function(){return Tt},"getAxisFormat"),Ze=d(function(t){wt=t},"setTickInterval"),Ue=d(function(){return wt},"getTickInterval"),qe=d(function(t){_t=t},"setTodayMarker"),Qe=d(function(){return _t},"getTodayMarker"),Xe=d(function(t){Q=t},"setDateFormat"),Je=d(function(){ht=!0},"enableInclusiveEndDates"),Ke=d(function(){return ht},"endDatesAreInclusive"),tn=d(function(){Et=!0},"enableTopAxis"),en=d(function(){return Et},"topAxisEnabled"),nn=d(function(t){St=t},"setDisplayMode"),rn=d(function(){return St},"getDisplayMode"),sn=d(function(){return Q},"getDateFormat"),an=d(function(t){dt=t.toLowerCase().split(/[\s,]+/)},"setIncludes"),on=d(function(){return dt},"getIncludes"),cn=d(function(t){ut=t.toLowerCase().split(/[\s,]+/)},"setExcludes"),ln=d(function(){return ut},"getExcludes"),dn=d(function(){return Dt},"getLinks"),un=d(function(t){ct=t,$t.push(t)},"addSection"),hn=d(function(){return $t},"getSections"),fn=d(function(){let t=se(),n=0;for(;!t&&n<10;)t=se(),n++;return Ct=H},"getTasks"),Kt=d(function(t,n,s,r){return!r.includes(t.format(n.trim()))&&(!(!s.includes("weekends")||t.isoWeekday()!==Xt[pt]&&t.isoWeekday()!==Xt[pt]+1)||!!s.includes(t.format("dddd").toLowerCase())||s.includes(t.format(n.trim())))},"isInvalidDate"),mn=d(function(t){At=t},"setWeekday"),yn=d(function(){return At},"getWeekday"),kn=d(function(t){pt=t},"setWeekend"),te=d(function(t,n,s,r){if(!s.length||t.manualEndTime)return;let i,c;i=t.startTime instanceof Date?V(t.startTime):V(t.startTime,n,!0),i=i.add(1,"d"),c=t.endTime instanceof Date?V(t.endTime):V(t.endTime,n,!0);const[h,A]=pn(i,c,n,s,r);t.endTime=h.toDate(),t.renderEndTime=A},"checkTaskDates"),pn=d(function(t,n,s,r,i){let c=!1,h=null;for(;t<=n;)c||(h=n.toDate()),c=Kt(t,s,r,i),c&&(n=n.add(1,"d")),t=t.add(1,"d");return[n,h]},"fixTaskDates"),It=d(function(t,n,s){s=s.trim();const r=/^after\s+(?<ids>[\d\w- ]+)/.exec(s);if(r!==null){let c=null;for(const A of r.groups.ids.split(" ")){let x=it(A);x!==void 0&&(!c||x.endTime>c.endTime)&&(c=x)}if(c)return c.endTime;const h=new Date;return h.setHours(0,0,0,0),h}let i=V(s,n.trim(),!0);if(i.isValid())return i.toDate();{mt.debug("Invalid date:"+s),mt.debug("With date format:"+n.trim());const c=new Date(s);if(c===void 0||isNaN(c.getTime())||c.getFullYear()<-1e4||c.getFullYear()>1e4)throw new Error("Invalid date:"+s);return c}},"getStartDate"),ee=d(function(t){const n=/^(\d+(?:\.\d+)?)([Mdhmswy]|ms)$/.exec(t.trim());return n!==null?[Number.parseFloat(n[1]),n[2]]:[NaN,"ms"]},"parseDuration"),ne=d(function(t,n,s,r=!1){s=s.trim();const i=/^until\s+(?<ids>[\d\w- ]+)/.exec(s);if(i!==null){let $=null;for(const W of i.groups.ids.split(" ")){let S=it(W);S!==void 0&&(!$||S.startTime<$.startTime)&&($=S)}if($)return $.startTime;const L=new Date;return L.setHours(0,0,0,0),L}let c=V(s,n.trim(),!0);if(c.isValid())return r&&(c=c.add(1,"d")),c.toDate();let h=V(t);const[A,x]=ee(s);if(!Number.isNaN(A)){const $=h.add(A,x);$.isValid()&&(h=$)}return h.toDate()},"getEndDate"),ie=0,lt=d(function(t){return t===void 0?"task"+(ie+=1):t},"parseId"),gn=d(function(t,n){let s;s=n.substr(0,1)===":"?n.substr(1,n.length):n;const r=s.split(","),i={};Yt(r,i,Jt);for(let h=0;h<r.length;h++)r[h]=r[h].trim();let c="";switch(r.length){case 1:i.id=lt(),i.startTime=t.endTime,c=r[0];break;case 2:i.id=lt(),i.startTime=It(void 0,Q,r[0]),c=r[1];break;case 3:i.id=lt(r[0]),i.startTime=It(void 0,Q,r[1]),c=r[2]}return c&&(i.endTime=ne(i.startTime,Q,c,ht),i.manualEndTime=V(c,"YYYY-MM-DD",!0).isValid(),te(i,Q,ut,dt)),i},"compileData"),bn=d(function(t,n){let s;s=n.substr(0,1)===":"?n.substr(1,n.length):n;const r=s.split(","),i={};Yt(r,i,Jt);for(let c=0;c<r.length;c++)r[c]=r[c].trim();switch(r.length){case 1:i.id=lt(),i.startTime={type:"prevTaskEnd",id:t},i.endTime={data:r[0]};break;case 2:i.id=lt(),i.startTime={type:"getStartDate",startData:r[0]},i.endTime={data:r[1]};break;case 3:i.id=lt(r[0]),i.startTime={type:"getStartDate",startData:r[1]},i.endTime={data:r[2]}}return i},"parseData"),H=[],re={},vn=d(function(t,n){const s={section:ct,type:ct,processed:!1,manualEndTime:!1,renderEndTime:null,raw:{data:n},task:t,classes:[]},r=bn(kt,n);s.raw.startTime=r.startTime,s.raw.endTime=r.endTime,s.id=r.id,s.prevTaskId=kt,s.active=r.active,s.done=r.done,s.crit=r.crit,s.milestone=r.milestone,s.vert=r.vert,s.order=Lt,Lt++;const i=H.push(s);kt=s.id,re[s.id]=i-1},"addTask"),it=d(function(t){const n=re[t];return H[n]},"findTaskById"),xn=d(function(t,n){const s={section:ct,type:ct,description:t,task:t,classes:[]},r=gn(xt,n);s.startTime=r.startTime,s.endTime=r.endTime,s.id=r.id,s.active=r.active,s.done=r.done,s.crit=r.crit,s.milestone=r.milestone,s.vert=r.vert,xt=s,Ct.push(s)},"addTaskOrg"),se=d(function(){const t=d(function(s){const r=H[s];let i="";switch(H[s].raw.startTime.type){case"prevTaskEnd":{const c=it(r.prevTaskId);r.startTime=c.endTime;break}case"getStartDate":i=It(void 0,Q,H[s].raw.startTime.startData),i&&(H[s].startTime=i)}return H[s].startTime&&(H[s].endTime=ne(H[s].startTime,Q,H[s].raw.endTime.data,ht),H[s].endTime&&(H[s].processed=!0,H[s].manualEndTime=V(H[s].raw.endTime.data,"YYYY-MM-DD",!0).isValid(),te(H[s],Q,ut,dt))),H[s].processed},"compileTask");let n=!0;for(const[s,r]of H.entries())t(s),n=n&&r.processed;return n},"compileTasks"),Tn=d(function(t,n){let s=n;ot().securityLevel!=="loose"&&(s=pe.sanitizeUrl(n)),t.split(",").forEach(function(r){it(r)!==void 0&&(oe(r,()=>{window.open(s,"_self")}),Dt.set(r,s))}),ae(t,"clickable")},"setLink"),ae=d(function(t,n){t.split(",").forEach(function(s){let r=it(s);r!==void 0&&r.classes.push(n)})},"setClass"),wn=d(function(t,n,s){if(ot().securityLevel!=="loose"||n===void 0)return;let r=[];if(typeof s=="string"){r=s.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);for(let i=0;i<r.length;i++){let c=r[i].trim();c.startsWith('"')&&c.endsWith('"')&&(c=c.substr(1,c.length-2)),r[i]=c}}r.length===0&&r.push(t),it(t)!==void 0&&oe(t,()=>{be.runFunc(n,...r)})},"setClickFun"),oe=d(function(t,n){Mt.push(function(){const s=document.querySelector(`[id="${t}"]`);s!==null&&s.addEventListener("click",function(){n()})},function(){const s=document.querySelector(`[id="${t}-text"]`);s!==null&&s.addEventListener("click",function(){n()})})},"pushFun"),_n=d(function(t,n,s){t.split(",").forEach(function(r){wn(r,n,s)}),ae(t,"clickable")},"setClickEvent"),Dn=d(function(t){Mt.forEach(function(n){n(t)})},"bindFunctions"),$n={getConfig:d(()=>ot().gantt,"getConfig"),clear:je,setDateFormat:Xe,getDateFormat:sn,enableInclusiveEndDates:Je,endDatesAreInclusive:Ke,enableTopAxis:tn,topAxisEnabled:en,setAxisFormat:Ve,getAxisFormat:Re,setTickInterval:Ze,getTickInterval:Ue,setTodayMarker:qe,getTodayMarker:Qe,setAccTitle:me,getAccTitle:fe,setDiagramTitle:he,getDiagramTitle:ue,setDisplayMode:nn,getDisplayMode:rn,setAccDescription:de,getAccDescription:le,addSection:un,getSections:hn,getTasks:fn,addTask:vn,findTaskById:it,addTaskOrg:xn,setIncludes:an,getIncludes:on,setExcludes:cn,getExcludes:ln,setClickEvent:_n,setLink:Tn,getLinks:dn,bindFunctions:Dn,parseDuration:ee,isInvalidDate:Kt,setWeekday:mn,getWeekday:yn,setWeekend:kn};function Yt(t,n,s){let r=!0;for(;r;)r=!1,s.forEach(function(i){const c=new RegExp("^\\s*"+i+"\\s*$");t[0].match(c)&&(n[i]=!0,t.shift(1),r=!0)})}d(Yt,"getTaskTags");var K,Cn=d(function(){mt.debug("Something is calling, setConf, remove the call")},"setConf"),ce={monday:$e,tuesday:De,wednesday:_e,thursday:we,friday:Te,saturday:xe,sunday:ve},Sn=d((t,n)=>{let s=[...t].map(()=>-1/0),r=[...t].sort((c,h)=>c.startTime-h.startTime||c.order-h.order),i=0;for(const c of r)for(let h=0;h<s.length;h++)if(c.startTime>=s[h]){s[h]=c.endTime,c.order=h+n,h>i&&(i=h);break}return i},"getMaxIntersections"),Mn={parser:Ge,db:$n,renderer:{setConf:Cn,draw:d(function(t,n,s,r){const i=ot().gantt,c=ot().securityLevel;let h;c==="sandbox"&&(h=bt("#i"+n));const A=bt(c==="sandbox"?h.nodes()[0].contentDocument.body:"body"),x=c==="sandbox"?h.nodes()[0].contentDocument:document,$=x.getElementById(n);(K=$.parentElement.offsetWidth)===void 0&&(K=1200),i.useWidth!==void 0&&(K=i.useWidth);const L=r.db.getTasks();let W=[];for(const k of L)W.push(k.type);W=Y(W);const S={};let D=2*i.topPadding;if(r.db.getDisplayMode()==="compact"||i.displayMode==="compact"){const k={};for(const b of L)k[b.section]===void 0?k[b.section]=[b]:k[b.section].push(b);let w=0;for(const b of Object.keys(k)){const g=Sn(k[b],w)+1;w+=g,D+=g*(i.barHeight+i.barGap),S[b]=g}}else{D+=L.length*(i.barHeight+i.barGap);for(const k of W)S[k]=L.filter(w=>w.type===k).length}$.setAttribute("viewBox","0 0 "+K+" "+D);const p=A.select(`[id="${n}"]`),y=Ce().domain([Se(L,function(k){return k.startTime}),Me(L,function(k){return k.endTime})]).rangeRound([0,K-i.leftPadding-i.rightPadding]);function M(k,w){const b=k.startTime,g=w.startTime;let f=0;return b>g?f=1:b<g&&(f=-1),f}function E(k,w,b){const g=i.barHeight,f=g+i.barGap,o=i.topPadding,m=i.leftPadding,u=Ae().domain([0,W.length]).range(["#00B9FA","#F95002"]).interpolate(Ee);z(f,o,m,w,b,k,r.db.getExcludes(),r.db.getIncludes()),j(m,o,w,b),P(k,f,o,m,g,u,w),B(f,o),O(m,o,w,b)}function P(k,w,b,g,f,o,m){k.sort((e,v)=>e.vert===v.vert?0:e.vert?1:-1);const u=[...new Set(k.map(e=>e.order))].map(e=>k.find(v=>v.order===e));p.append("g").selectAll("rect").data(u).enter().append("rect").attr("x",0).attr("y",function(e,v){return e.order*w+b-2}).attr("width",function(){return m-i.rightPadding/2}).attr("height",w).attr("class",function(e){for(const[v,a]of W.entries())if(e.type===a)return"section section"+v%i.numberSectionStyles;return"section section0"}).enter();const l=p.append("g").selectAll("rect").data(k).enter(),T=r.db.getLinks();if(l.append("rect").attr("id",function(e){return e.id}).attr("rx",3).attr("ry",3).attr("x",function(e){return e.milestone?y(e.startTime)+g+.5*(y(e.endTime)-y(e.startTime))-.5*f:y(e.startTime)+g}).attr("y",function(e,v){return v=e.order,e.vert?i.gridLineStartPadding:v*w+b}).attr("width",function(e){return e.milestone?f:e.vert?.08*f:y(e.renderEndTime||e.endTime)-y(e.startTime)}).attr("height",function(e){return e.vert?L.length*(i.barHeight+i.barGap)+2*i.barHeight:f}).attr("transform-origin",function(e,v){return v=e.order,(y(e.startTime)+g+.5*(y(e.endTime)-y(e.startTime))).toString()+"px "+(v*w+b+.5*f).toString()+"px"}).attr("class",function(e){let v="";e.classes.length>0&&(v=e.classes.join(" "));let a=0;for(const[I,F]of W.entries())e.type===F&&(a=I%i.numberSectionStyles);let _="";return e.active?e.crit?_+=" activeCrit":_=" active":e.done?_=e.crit?" doneCrit":" done":e.crit&&(_+=" crit"),_.length===0&&(_=" task"),e.milestone&&(_=" milestone "+_),e.vert&&(_=" vert "+_),_+=a,_+=" "+v,"task"+_}),l.append("text").attr("id",function(e){return e.id+"-text"}).text(function(e){return e.task}).attr("font-size",i.fontSize).attr("x",function(e){let v=y(e.startTime),a=y(e.renderEndTime||e.endTime);if(e.milestone&&(v+=.5*(y(e.endTime)-y(e.startTime))-.5*f,a=v+f),e.vert)return y(e.startTime)+g;const _=this.getBBox().width;return _>a-v?a+_+1.5*i.leftPadding>m?v+g-5:a+g+5:(a-v)/2+v+g}).attr("y",function(e,v){return e.vert?i.gridLineStartPadding+L.length*(i.barHeight+i.barGap)+60:e.order*w+i.barHeight/2+(i.fontSize/2-2)+b}).attr("text-height",f).attr("class",function(e){const v=y(e.startTime);let a=y(e.endTime);e.milestone&&(a=v+f);const _=this.getBBox().width;let I="";e.classes.length>0&&(I=e.classes.join(" "));let F=0;for(const[U,tt]of W.entries())e.type===tt&&(F=U%i.numberSectionStyles);let C="";return e.active&&(C=e.crit?"activeCritText"+F:"activeText"+F),e.done?C=e.crit?C+" doneCritText"+F:C+" doneText"+F:e.crit&&(C=C+" critText"+F),e.milestone&&(C+=" milestoneText"),e.vert&&(C+=" vertText"),_>a-v?a+_+1.5*i.leftPadding>m?I+" taskTextOutsideLeft taskTextOutside"+F+" "+C:I+" taskTextOutsideRight taskTextOutside"+F+" "+C+" width-"+_:I+" taskText taskText"+F+" "+C+" width-"+_}),ot().securityLevel==="sandbox"){let e;e=bt("#i"+n);const v=e.nodes()[0].contentDocument;l.filter(function(a){return T.has(a.id)}).each(function(a){var _=v.querySelector("#"+a.id),I=v.querySelector("#"+a.id+"-text");const F=_.parentNode;var C=v.createElement("a");C.setAttribute("xlink:href",T.get(a.id)),C.setAttribute("target","_top"),F.appendChild(C),C.appendChild(_),C.appendChild(I)})}}function z(k,w,b,g,f,o,m,u){if(m.length===0&&u.length===0)return;let l,T;for(const{startTime:I,endTime:F}of o)(l===void 0||I<l)&&(l=I),(T===void 0||F>T)&&(T=F);if(!l||!T)return;if(V(T).diff(V(l),"year")>5)return void mt.warn("The difference between the min and max time is more than 5 years. This will cause performance issues. Skipping drawing exclude days.");const e=r.db.getDateFormat(),v=[];let a=null,_=V(l);for(;_.valueOf()<=T;)r.db.isInvalidDate(_,e,m,u)?a?a.end=_:a={start:_,end:_}:a&&(v.push(a),a=null),_=_.add(1,"d");p.append("g").selectAll("rect").data(v).enter().append("rect").attr("id",function(I){return"exclude-"+I.start.format("YYYY-MM-DD")}).attr("x",function(I){return y(I.start)+b}).attr("y",i.gridLineStartPadding).attr("width",function(I){const F=I.end.add(1,"day");return y(F)-y(I.start)}).attr("height",f-w-i.gridLineStartPadding).attr("transform-origin",function(I,F){return(y(I.start)+b+.5*(y(I.end)-y(I.start))).toString()+"px "+(F*k+.5*f).toString()+"px"}).attr("class","exclude-range")}function j(k,w,b,g){let f=(o=y,jt(3,o)).tickSize(-g+w+i.gridLineStartPadding).tickFormat(Wt(r.db.getAxisFormat()||i.axisFormat||"%Y-%m-%d"));var o;const m=/^([1-9]\d*)(millisecond|second|minute|hour|day|week|month)$/.exec(r.db.getTickInterval()||i.tickInterval);if(m!==null){const u=m[1],l=m[2],T=r.db.getWeekday()||i.weekday;switch(l){case"millisecond":f.ticks(Nt.every(u));break;case"second":f.ticks(Ht.every(u));break;case"minute":f.ticks(Bt.every(u));break;case"hour":f.ticks(zt.every(u));break;case"day":f.ticks(Pt.every(u));break;case"week":f.ticks(ce[T].every(u));break;case"month":f.ticks(Ot.every(u))}}if(p.append("g").attr("class","grid").attr("transform","translate("+k+", "+(g-50)+")").call(f).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10).attr("dy","1em"),r.db.topAxisEnabled()||i.topAxis){let u=function(l){return jt(1,l)}(y).tickSize(-g+w+i.gridLineStartPadding).tickFormat(Wt(r.db.getAxisFormat()||i.axisFormat||"%Y-%m-%d"));if(m!==null){const l=m[1],T=m[2],e=r.db.getWeekday()||i.weekday;switch(T){case"millisecond":u.ticks(Nt.every(l));break;case"second":u.ticks(Ht.every(l));break;case"minute":u.ticks(Bt.every(l));break;case"hour":u.ticks(zt.every(l));break;case"day":u.ticks(Pt.every(l));break;case"week":u.ticks(ce[e].every(l));break;case"month":u.ticks(Ot.every(l))}}p.append("g").attr("class","grid").attr("transform","translate("+k+", "+w+")").call(u).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10)}}function B(k,w){let b=0;const g=Object.keys(S).map(f=>[f,S[f]]);p.append("g").selectAll("text").data(g).enter().append(function(f){const o=f[0].split(ke.lineBreakRegex),m=-(o.length-1)/2,u=x.createElementNS("http://www.w3.org/2000/svg","text");u.setAttribute("dy",m+"em");for(const[l,T]of o.entries()){const e=x.createElementNS("http://www.w3.org/2000/svg","tspan");e.setAttribute("alignment-baseline","central"),e.setAttribute("x","10"),l>0&&e.setAttribute("dy","1em"),e.textContent=T,u.appendChild(e)}return u}).attr("x",10).attr("y",function(f,o){if(!(o>0))return f[1]*k/2+w;for(let m=0;m<o;m++)return b+=g[o-1][1],f[1]*k/2+b*k+w}).attr("font-size",i.sectionFontSize).attr("class",function(f){for(const[o,m]of W.entries())if(f[0]===m)return"sectionTitle sectionTitle"+o%i.numberSectionStyles;return"sectionTitle"})}function O(k,w,b,g){const f=r.db.getTodayMarker();if(f==="off")return;const o=p.append("g").attr("class","today"),m=new Date,u=o.append("line");u.attr("x1",y(m)+k).attr("x2",y(m)+k).attr("y1",i.titleTopMargin).attr("y2",g-i.titleTopMargin).attr("class","today"),f!==""&&u.attr("style",f.replace(/,/g,";"))}function Y(k){const w={},b=[];for(let g=0,f=k.length;g<f;++g)Object.prototype.hasOwnProperty.call(w,k[g])||(w[k[g]]=!0,b.push(k[g]));return b}d(M,"taskCompare"),L.sort(M),E(L,K,D),ye(p,D,K,i.useMaxWidth),p.append("text").text(r.db.getDiagramTitle()).attr("x",K/2).attr("y",i.titleTopMargin).attr("class","titleText"),d(E,"makeGantt"),d(P,"drawRects"),d(z,"drawExcludeDays"),d(j,"makeGrid"),d(B,"vertLabels"),d(O,"drawToday"),d(Y,"checkUnique")},"draw")},styles:d(t=>`
  .mermaid-main-font {
        font-family: ${t.fontFamily};
  }

  .exclude-range {
    fill: ${t.excludeBkgColor};
  }

  .section {
    stroke: none;
    opacity: 0.2;
  }

  .section0 {
    fill: ${t.sectionBkgColor};
  }

  .section2 {
    fill: ${t.sectionBkgColor2};
  }

  .section1,
  .section3 {
    fill: ${t.altSectionBkgColor};
    opacity: 0.2;
  }

  .sectionTitle0 {
    fill: ${t.titleColor};
  }

  .sectionTitle1 {
    fill: ${t.titleColor};
  }

  .sectionTitle2 {
    fill: ${t.titleColor};
  }

  .sectionTitle3 {
    fill: ${t.titleColor};
  }

  .sectionTitle {
    text-anchor: start;
    font-family: ${t.fontFamily};
  }


  /* Grid and axis */

  .grid .tick {
    stroke: ${t.gridColor};
    opacity: 0.8;
    shape-rendering: crispEdges;
  }

  .grid .tick text {
    font-family: ${t.fontFamily};
    fill: ${t.textColor};
  }

  .grid path {
    stroke-width: 0;
  }


  /* Today line */

  .today {
    fill: none;
    stroke: ${t.todayLineColor};
    stroke-width: 2px;
  }


  /* Task styling */

  /* Default task */

  .task {
    stroke-width: 2;
  }

  .taskText {
    text-anchor: middle;
    font-family: ${t.fontFamily};
  }

  .taskTextOutsideRight {
    fill: ${t.taskTextDarkColor};
    text-anchor: start;
    font-family: ${t.fontFamily};
  }

  .taskTextOutsideLeft {
    fill: ${t.taskTextDarkColor};
    text-anchor: end;
  }


  /* Special case clickable */

  .task.clickable {
    cursor: pointer;
  }

  .taskText.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideLeft.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideRight.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }


  /* Specific task settings for the sections*/

  .taskText0,
  .taskText1,
  .taskText2,
  .taskText3 {
    fill: ${t.taskTextColor};
  }

  .task0,
  .task1,
  .task2,
  .task3 {
    fill: ${t.taskBkgColor};
    stroke: ${t.taskBorderColor};
  }

  .taskTextOutside0,
  .taskTextOutside2
  {
    fill: ${t.taskTextOutsideColor};
  }

  .taskTextOutside1,
  .taskTextOutside3 {
    fill: ${t.taskTextOutsideColor};
  }


  /* Active task */

  .active0,
  .active1,
  .active2,
  .active3 {
    fill: ${t.activeTaskBkgColor};
    stroke: ${t.activeTaskBorderColor};
  }

  .activeText0,
  .activeText1,
  .activeText2,
  .activeText3 {
    fill: ${t.taskTextDarkColor} !important;
  }


  /* Completed task */

  .done0,
  .done1,
  .done2,
  .done3 {
    stroke: ${t.doneTaskBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
  }

  .doneText0,
  .doneText1,
  .doneText2,
  .doneText3 {
    fill: ${t.taskTextDarkColor} !important;
  }


  /* Tasks on the critical line */

  .crit0,
  .crit1,
  .crit2,
  .crit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.critBkgColor};
    stroke-width: 2;
  }

  .activeCrit0,
  .activeCrit1,
  .activeCrit2,
  .activeCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.activeTaskBkgColor};
    stroke-width: 2;
  }

  .doneCrit0,
  .doneCrit1,
  .doneCrit2,
  .doneCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
    cursor: pointer;
    shape-rendering: crispEdges;
  }

  .milestone {
    transform: rotate(45deg) scale(0.8,0.8);
  }

  .milestoneText {
    font-style: italic;
  }
  .doneCritText0,
  .doneCritText1,
  .doneCritText2,
  .doneCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  .vert {
    stroke: ${t.vertLineColor};
  }

  .vertText {
    font-size: 15px;
    text-anchor: middle;
    fill: ${t.vertLineColor} !important;
  }

  .activeCritText0,
  .activeCritText1,
  .activeCritText2,
  .activeCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  .titleText {
    text-anchor: middle;
    font-size: 18px;
    fill: ${t.titleColor||t.textColor};
    font-family: ${t.fontFamily};
  }
`,"getStyles")};export{Mn as diagram};
