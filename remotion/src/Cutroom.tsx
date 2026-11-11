import React from 'react';
import type {Caption} from '@remotion/captions';
import {loadFont} from '@remotion/fonts';
import {Interactive, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

// loadFont itself holds delayRender until each bundled font is ready.
void Promise.all([
  loadFont({family:'Cutroom Sans',url:staticFile('CutroomSans-ExtraBold.ttf')}),
  loadFont({family:'Cutroom Studio',url:staticFile('CutroomStudio-Bold.ttf')}),
]);

type CaptionProps = {captions:Caption[]; accent:string; size:number; font:string; y:number; animation:string; style?:React.CSSProperties};
const CaptionContent:React.FC<CaptionProps> = ({captions,accent,size,font,y,animation,style}) => {
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const ms=frame/fps*1000;
  const enter=interpolate(frame,[0,fps*.12],[0,1],{extrapolateRight:'clamp'});
  return <div style={{position:'absolute',left:100,top:y-60,width:880,textAlign:'center',
    fontFamily:font,fontSize:size,lineHeight:1.12,fontWeight:800,color:'white',
    textShadow:'0 3px 3px #000, 0 0 6px #000, 2px 0 2px #000, -2px 0 2px #000',
    whiteSpace:'pre-wrap',textWrap:'balance',opacity:enter,
    transform:animation==='highlight'?`scale(${.96+enter*.04})`:undefined,...style}}>
    {captions.map((c,i)=><span key={i} style={{color:animation==='highlight'&&ms>=c.startMs&&ms<c.endMs?accent:'white'}}>{c.text}</span>)}
  </div>;
};
export const CutroomCaptions=Interactive.withSchema({Component:CaptionContent,componentName:'<CutroomCaptions>',wrapInSequence:true,
  schema:{...Interactive.captionsSchema,accent:{type:'color',default:'#B5FF73'},
    size:{type:'number',hiddenFromList:false,default:82,min:54,max:110},font:{type:'string',default:'Cutroom Sans'},
    y:{type:'number',hiddenFromList:false,default:1330},animation:{type:'string',default:'highlight'}}});

type TitleProps={text:string; accent:string; y:number; motion:string; size:number; style?:React.CSSProperties};
const TitleContent:React.FC<TitleProps>=({text,accent,y,motion,size,style})=>{
  const frame=useCurrentFrame(); const {fps,durationInFrames}=useVideoConfig();
  const start=interpolate(frame,[0,fps*.16],[0,1],{extrapolateRight:'clamp'});
  const end=interpolate(frame,[Math.max(0,durationInFrames-fps*.15),durationInFrames],[1,0],{extrapolateLeft:'clamp'});
  return <div style={{position:'absolute',top:y,left:110,width:860,color:'white',fontFamily:'Cutroom Sans',
    fontSize:size,lineHeight:1.15,textAlign:'center',fontWeight:800,textWrap:'balance',
    textShadow:'0 3px 5px #000, 0 0 8px #000',opacity:Math.min(start,end),
    transform:motion==='pop'?`scale(${.92+.08*start})`:`translateY(${12*(1-start)}px)`,...style}}>
    <div style={{width:56,height:5,background:accent,margin:'0 auto 18px',borderRadius:3}}/>{text}
  </div>;
};
export const CutroomTitle=Interactive.withSchema({Component:TitleContent,componentName:'<CutroomTitle>',wrapInSequence:true,
  schema:{text:{type:'text-content',default:'Look closer'},accent:{type:'color',default:'#B5FF73'},
    y:{type:'number',hiddenFromList:false,default:370},motion:{type:'string',default:'pop'},size:{type:'number',hiddenFromList:false,default:68,min:36,max:100}}});
