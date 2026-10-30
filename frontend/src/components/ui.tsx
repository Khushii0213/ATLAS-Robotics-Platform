import {ReactNode} from 'react';
export function Panel({title,children,action}:{title?:string;children:ReactNode;action?:ReactNode}){return <section className="panel">{title&&<header><span>{title}</span>{action}</header>}<div className="panel-body">{children}</div></section>}
export function Badge({value}:{value:string}){return <span className={'badge '+value.toLowerCase().replaceAll('_','-')}>{value.replaceAll('_',' ')}</span>}
export function Metric({label,value,detail}:{label:string;value:string|number;detail?:string}){return <div className="metric"><small>{label}</small><strong>{value}</strong>{detail&&<em>{detail}</em>}</div>}
export function Empty({children}:{children:ReactNode}){return <div className="empty">{children}</div>}
