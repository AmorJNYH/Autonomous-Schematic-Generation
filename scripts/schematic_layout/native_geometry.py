"""Finite native SVG ink and causal differences, never a nearest-object matcher.

The supported geometry channel is mm, identity transform, MLZ round strokes
and a finite unfilled absolute circular-A diameter-semicircle profile.
All visible primitives and hidden full-text companions participate in equality;
unsupported containers/effects are rejected rather than discarded.
"""
from collections import Counter
from fractions import Fraction
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

# These are coverage bounds, not matching tolerances or permissions to ignore
# small collisions. Every arc chord carries its own inflated stroke capsule.
ARC_SAGITTA_MM = .0002
ARC_SERIALIZATION_MM = .0002
ARC_SEGMENT_BUDGET = 4096

def _arc_serialization_envelope(radius):
    # A near-diameter circle is ill-conditioned: endpoint/radius rounding can
    # move its centre by sqrt(r*epsilon), not merely epsilon. Each endpoint's
    # two-axis error is bounded by sqrt(2)*epsilon; midpoint has that bound and
    # the true half-chord is at least max(0,r-sqrt(2)*epsilon). Bound the possible
    # centre height using a radius at most r+epsilon, avoiding cancellation.
    eps=ARC_SERIALIZATION_MM
    endpoint=math.nextafter(math.sqrt(2)*eps,math.inf)
    upper=math.nextafter(radius+eps,math.inf)
    lower=max(0,math.nextafter(radius-endpoint,-math.inf))
    height=math.nextafter(math.sqrt((upper-lower)*(upper+lower)),math.inf)
    # Centre translation plus radial error protects corresponding circle
    # points. Sweep endpoint extension/axis rotation is also bounded: for a
    # diameter perturbation, r*asin(h/r) <= pi*h/2 (and similarly for endpoint
    # axis error). Four times the centre+radius envelope dominates their sum,
    # including the small-radius case where the endpoint error exceeds r.
    return math.nextafter(4*(endpoint+height+eps),math.inf)

def _arc_decimal(raw):
    # Native fixed decimal coordinates only. Bounded exact rational arithmetic
    # proves a diameter, avoiding an epsilon that silently accepts a different
    # circle centre or SVG's radius-correction branch near a diameter.
    if (len(raw)>32 or not re.fullmatch(r'[-+]?(?:\d+(?:\.\d{0,10})?|\.\d{1,10})',raw)
            or abs(finite(raw))>10000):
        raise ValueError('unsupported circular-A numeric profile')
    return Fraction(raw)

def stroke_path(d, width):
    """Conservative native ink capsules; never physical conductor identity.

    Only absolute, unrotated, exact circular diameter semicircles qualify.
    Both sweep/large flags are retained in primitive equality. A half circle
    has the same pi extent for either large flag; sweep selects its side.
    Unsupported curves raise instead of disappearing from the foreground.
    """
    width=finite(width)
    if width<0: raise ValueError('negative stroke')
    if 'A' not in d:
        return [[list(a),list(b),width] for a,b in linear_path(d)]
    if width>10000: raise ValueError('unsupported circular-A stroke magnitude')
    tokens=re.findall(r'[A-Za-z]|'+NUM,d)
    if re.sub(r'[\s,]','',d)!=''.join(tokens): raise ValueError('unknown path syntax')
    if len(tokens)>20000: raise ValueError('circular-A path token budget exceeded')
    out=[]; current=None; start=None; raw_current=None; raw_start=None; command=None; i=0; closed=False
    def append_segment(segment):
        # Every branch, including Z and later subpaths, shares the same bound.
        if len(out)>=ARC_SEGMENT_BUDGET: raise ValueError('circular-A segment budget exceeded')
        out.append(segment)
    while i<len(tokens):
        if tokens[i].isalpha():
            command=tokens[i]; i+=1
            if command not in ('M','L','A','Z'): raise ValueError('unsupported native path command')
            if command=='Z':
                if current is None or start is None or closed: raise ValueError('invalid path closure')
                append_segment([list(current),list(start),width]);current=start;raw_current=raw_start;command=None;closed=True
                continue
            if i==len(tokens): raise ValueError('malformed native path')
        count=7 if command=='A' else 2
        if command not in ('M','L','A') or i+count>len(tokens) or any(t.isalpha() for t in tokens[i:i+count]):
            raise ValueError('malformed native path')
        args=tokens[i:i+count];i+=count
        if command in ('M','L'):
            for token in args: _arc_decimal(token)
            p=tuple(finite(t) for t in args)
            if command=='M':start=current=p;raw_start=raw_current=args;command='L'
            else:
                if current is None: raise ValueError('line without move')
                append_segment([list(current),list(p),width]);current=p;raw_current=args
        else:
            if current is None: raise ValueError('arc without move')
            rx,ry,rotation,large,sweep,x,y=args
            values=[finite(t) for t in args]
            if values[0]<=0 or values[0]!=values[1] or values[2]!=0 or large not in ('0','1') or sweep not in ('0','1'):
                raise ValueError('unsupported circular-A radius/rotation/flags')
            r=_arc_decimal(rx)
            if _arc_decimal(ry)!=r: raise ValueError('not an exact circular-A radius')
            ax,ay=map(_arc_decimal,raw_current);bx,by=map(_arc_decimal,(x,y))
            if (bx-ax)**2+(by-ay)**2!=4*r*r:
                raise ValueError('circular-A endpoints must be an exact diameter')
            radius=float(r);p=(values[5],values[6]);center=(float((ax+bx)/2),float((ay+by)/2))
            n=max(1,math.ceil(math.pi*math.sqrt(radius/(8*ARC_SAGITTA_MM))))
            if len(out)+n>ARC_SEGMENT_BUDGET: raise ValueError('circular-A segment budget exceeded')
            step=math.pi/n;direction=1 if sweep=='1' else -1
            theta=math.atan2(current[1]-center[1],current[0]-center[0])
            # 1-cos(t/2) <= t*t/8 avoids cancellation and underestimating
            # sagitta. Floating evaluation is padded well beyond binary ulps
            # over this bounded native coordinate/radius profile. The same
            # margin includes four-decimal native serialization uncertainty.
            numeric=64*math.ulp(max(1.,radius,*map(abs,center),*map(abs,current),*map(abs,p)))
            error=math.nextafter(radius*step*step/8+_arc_serialization_envelope(radius)+numeric,math.inf)
            effective_width=math.nextafter(width+2*error,math.inf)
            finite(effective_width)
            previous=current
            for j in range(1,n+1):
                angle=theta+direction*step*j
                q=p if j==n else (center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle))
                append_segment([list(previous),list(q),effective_width]);previous=q
            current=p;raw_current=[x,y]
        closed=False
        if len(out)>ARC_SEGMENT_BUDGET: raise ValueError('circular-A segment budget exceeded')
    if len(out)>ARC_SEGMENT_BUDGET: raise ValueError('circular-A segment budget exceeded')
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
                if tag=='path':
                    d=attrs.get('d','')
                    if 'A' in d and (st.get('fill','none')!='none' or 'stroked-text' in cc):
                        raise ValueError('filled/curved glyph circular-A profile unsupported')
                    if 'A' in d:
                        if (opacity!=1 or finite(st.get('stroke-opacity','1'))!=1 or st['fill-opacity']!=1
                                or width<=0 or st.get('stroke','none')=='none'
                                or st.get('stroke-linecap')!='round' or st.get('stroke-linejoin')!='round'):
                            raise ValueError('unsupported circular-A paint')
                        dash=st.get('stroke-dasharray','none')
                        if dash!='none':
                            if not re.fullmatch(r'[\d.eE+\-\s,]+',dash): raise ValueError('unsupported circular-A dash')
                            values=[finite(v) for v in re.split(r'[\s,]+',dash.strip())]
                            if len(values)<2 or any(v<=0 for v in values): raise ValueError('unsupported circular-A dash')
                    stroke_path(d,width)
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
            if o['tag']=='path':
                if glyph:
                    out += [[list(a),list(b),width] for a,b in linear_path(a['d'])]*count
                else:
                    out += stroke_path(a['d'],width)*count
                continue
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
