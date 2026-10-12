"""Finite native SVG ink and causal differences, never a nearest-object matcher.

The supported geometry channel is mm, identity transform, MLZ round strokes.
All visible primitives and hidden full-text companions participate in equality;
unsupported containers/effects are rejected rather than discarded.
"""
from collections import Counter
import json
import math
import re
import xml.etree.ElementTree as ET

NUM = r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?'
STYLE = {'fill','fill-opacity','stroke','stroke-opacity','stroke-width',
         'stroke-linecap','stroke-linejoin','stroke-dasharray','opacity'}

def finite(x):
    n=float(x)
    if not math.isfinite(n): raise ValueError('nonfinite native geometry')
    return n

def linear_path(d):
    tokens=re.findall(r'[A-Za-z]|'+NUM,d)
    if re.sub(r'[\s,]','',d) != ''.join(tokens): raise ValueError('unknown path syntax')
    out=[]; current=None; start=None; command=None; i=0
    while i<len(tokens):
        if tokens[i].isalpha():
            command=tokens[i]; i+=1
            if command not in ('M','L','Z'): raise ValueError('unsupported native path command')
            if command=='Z':
                if current is None or start is None: raise ValueError('invalid path closure')
                out.append((current,start)); current=start; command=None; continue
        if command not in ('M','L') or i+1>=len(tokens) or tokens[i+1].isalpha():
            raise ValueError('malformed native path')
        p=(finite(tokens[i]),finite(tokens[i+1])); i+=2
        if command=='M': start=current=p; command='L'
        else:
            if current is None: raise ValueError('line without move')
            out.append((current,p)); current=p
    return out

class SVG:
    def __init__(self, text):
        root=ET.fromstring(text); self.primitives=Counter(); self.texts=Counter(); self.objects={}
        vb=[finite(n) for n in root.attrib.get('viewBox','').split()]
        if len(vb)!=4 or vb[:2]!=[0,0] or min(vb[2:])<=0: raise ValueError('unsupported native viewport')
        for attr,n in zip(('width','height'),vb[2:]):
            raw=root.attrib.get(attr,'')
            if not raw.endswith('mm') or abs(finite(raw[:-2])-n)>1e-6: raise ValueError('native units not millimetres')
        self.page=vb[2:]
        def visit(e, inherited, opacity, classes, transforms):
            tag=e.tag.rsplit('}',1)[-1]; st=dict(inherited); local={}
            for pair in e.attrib.get('style','').split(';'):
                if pair.strip():
                    if ':' not in pair: raise ValueError('malformed SVG style')
                    k,v=pair.split(':',1); local[k.strip()]=v.strip()
            if set(local)-STYLE: raise ValueError('unsupported SVG style')
            local.update({k:v for k,v in e.attrib.items() if k in STYLE})
            opacity*=finite(local.pop('opacity','1')); st.update(local)
            if not 0<=opacity<=1: raise ValueError('invalid opacity')
            trans=e.attrib.get('transform')
            tt=transforms+([trans] if trans and trans!='translate(0 0) scale(1 1)' else [])
            if any(k in e.attrib for k in ('clip-path','filter','mask','display','visibility')):
                raise ValueError('unsupported native visibility/effect')
            for k in ('fill-opacity','stroke-opacity'):
                if not 0<=finite(st.get(k,'1'))<=1: raise ValueError('invalid stroke opacity')
            # Compare the resolved SVG paint, not its optional spelling. KiCad
            # may move an unchanged path between groups when an annotation is
            # added, leaving default fill-opacity implicit instead of 1.0000.
            # Inheritance has already been resolved; non-default values remain
            # distinct and unknown CSS/effects are still rejected below.
            st['fill-opacity']=finite(st.get('fill-opacity','1'))
            width=finite(st.get('stroke-width','0'))
            if width<0: raise ValueError('negative stroke')
            cc=classes+([e.attrib['class']] if 'class' in e.attrib else [])
            attrs={k:v for k,v in e.attrib.items() if k not in STYLE|{'style','id','transform'}}
            obj={'tag':tag,'attrs':attrs,'style':st,'opacity':opacity,'classes':cc,'transforms':tt}
            if tag=='text':
                if opacity!=0: raise ValueError('visible SVG text not stroked glyphs')
                obj['literal']=''.join(e.itertext()); self.texts[json.dumps(obj,sort_keys=True,ensure_ascii=False)]+=1
                return
            if tag in ('title','desc'): return
            if tag not in ('svg','g','path','rect','circle','ellipse','line','polyline','polygon'):
                raise ValueError('unsupported SVG object '+tag)
            visible=opacity>0 and ((st.get('fill','none')!='none' and finite(st.get('fill-opacity','1'))>0)
                       or (st.get('stroke','none')!='none' and finite(st.get('stroke-opacity','1'))>0 and width>0))
            if tag not in ('svg','g') and visible:
                if tt: raise ValueError('unsupported visible native transform')
                if tag=='path': linear_path(attrs.get('d',''))
                for k in ('x','y','x1','x2','y1','y2','r','rx','ry','cx','cy','width','height'):
                    if k in attrs: finite(attrs[k])
                if tag in ('polyline','polygon'):
                    raw=attrs.get('points','');tokens=re.findall(NUM,raw)
                    if re.sub(r'[\s,]','',raw)!=''.join(tokens) or not tokens or len(tokens)%2:
                        raise ValueError('unsupported polygon points')
                    for n in tokens: finite(n)
                key=json.dumps(obj,sort_keys=True,ensure_ascii=False)
                self.primitives[key]+=1; self.objects[key]=obj
            for child in e: visit(child,st,opacity,cc,tt)
        visit(root,{},1,[],[])

    def segments(self, keys=None, glyph=False):
        out=[]
        for k,count in (self.primitives if keys is None else keys).items():
            o=self.objects[k]; st=o['style']; a=o['attrs']; width=finite(st.get('stroke-width','0'))
            if st.get('fill','none')!='none' or width<=0 or st.get('stroke-dasharray','none')!='none':
                raise ValueError('not unfilled solid stroke')
            if st.get('stroke-linecap')!='round' or st.get('stroke-linejoin')!='round':
                raise ValueError('unqualified cap/join')
            if glyph and (o['tag']!='path' or 'stroked-text' not in o['classes']):
                raise ValueError('deleted primitive not stroked text')
            if o['tag']=='path': pairs=linear_path(a['d'])
            elif o['tag']=='rect' and finite(a.get('rx','0'))==0:
                x,y,w,h=(finite(a.get(k,'0')) for k in ('x','y','width','height'))
                if min(w,h)<=0: raise ValueError('invalid rectangle')
                ps=[(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]; pairs=list(zip(ps,ps[1:]))
            else: raise ValueError('unsupported target stroke shape')
            out += [[list(a),list(b),width] for a,b in pairs]*count
        if not out: raise ValueError('empty target ink')
        return out

def bounds(segments):
    if not segments: raise ValueError('empty ink')
    return [min(min(a[0],b[0])-w/2 for a,b,w in segments),
            min(min(a[1],b[1])-w/2 for a,b,w in segments),
            max(max(a[0],b[0])+w/2 for a,b,w in segments),
            max(max(a[1],b[1])+w/2 for a,b,w in segments)]

def removal(old,new):
    deleted=old.primitives-new.primitives; added=new.primitives-old.primitives
    dt=old.texts-new.texts; at=new.texts-old.texts
    if not deleted or added or at or sum(dt.values())!=1: raise ValueError('nonunique/noncausal text removal')
    ink=old.segments(deleted,glyph=True); literal=json.loads(next(iter(dt)))['literal']
    if not literal: raise ValueError('empty full shown literal')
    return {'literal':literal,'segments':ink,'box':bounds(ink),
            'deleted_primitives':sum(deleted.values()),'deleted_texts':1}

def point_segment(p,a,b):
    x,y=b[0]-a[0],b[1]-a[1]; q=x*x+y*y
    t=max(0,min(1,((p[0]-a[0])*x+(p[1]-a[1])*y)/q)) if q else 0
    return math.hypot(p[0]-a[0]-t*x,p[1]-a[1]-t*y)

def distance(a,b,c,d):
    def cross(p,q,r): return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    if (cross(a,b,c)*cross(a,b,d)<=0 and cross(c,d,a)*cross(c,d,b)<=0
        and max(min(a[0],b[0]),min(c[0],d[0]))<=min(max(a[0],b[0]),max(c[0],d[0]))
        and max(min(a[1],b[1]),min(c[1],d[1]))<=min(max(a[1],b[1]),max(c[1],d[1]))): return 0
    return min(point_segment(a,c,d),point_segment(b,c,d),point_segment(c,a,b),point_segment(d,a,b))

def ink_gap(a,b):
    return min(distance(p,q,r,s)-(w+v)/2 for p,q,w in a for r,s,v in b)
