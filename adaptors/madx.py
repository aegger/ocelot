from pylab import *
import numpy.fft as fft


class TrackingInfo:
    def __init__(self):
        pass


class TFS:
    def __init__(self, fname):
        self.params = {}
        self.column_names = []
        self.column_values = {}
        self.read(fname)

    def read(self, fname):
        seen_none = False
        lines = open(fname).read().split('\n')
        for l in lines:
            if seen_none: break
            tk = l.split()
            if len(tk) > 3 and tk[0] == '@':
                # print tk
                self.params[tk[1]] = tk[3]
            elif len(tk) > 3 and tk[0] == '@':
                self.params[tk[1]] = tk[3]
            elif len(tk) > 1 and tk[0] == '$':
                continue
            elif len(tk) > 1 and tk[0] == '*':
                for t in tk[1:]:
                    self.column_names.append(t)
                    self.column_values[t] = []
            else:
                if 'nan' in tk or '-nan' in tk:
                    seen_none = True
                    break

                for i in range(len(tk)):
                    try:
                        self.column_values[self.column_names[i]].append(float(tk[i]))
                    except:
                        self.column_values[self.column_names[i]].append(tk[i])


def get_tunes(tr_x, tr_y):
    v = np.zeros(len(tr_x))
    for i in range(len(v)): v[i] = float(tr_x[i])

    u = np.zeros(len(tr_y))
    for i in range(len(u)): u[i] = float(tr_y[i])

    sv = fft.fft(v)
    su = fft.fft(u)

    sv = np.abs(sv * np.conj(sv))
    su = np.abs(su * np.conj(su))

    freq = np.fft.fftfreq(len(sv))

    return (freq[np.argmax(sv[1:len(sv) / 2 - 1], axis=0)], freq[np.argmax(su[1:len(su) / 2 - 1], axis=0)])


def rename_type(etype):
    type_replacement = {
        'quadrupole': 'Quadrupole',
        'sextupole': 'Sextupole',
        'marker': 'Marker',
        'hkicker': 'Hcor',
        'vkicker': 'Vcor',
        'kicker': 'Hcor',
        'instrument': 'Drift',
        'sbend': 'SBend',
        'rbend': 'RBend',
        'bend': 'Bend',
        'rcollimator': 'Marker',
        'ecollimator': 'Marker',
        'matrix': 'Matrix',
        'monitor': 'Monitor',
        'sequence': 'Marker'
    }

    if etype in type_replacement: return type_replacement[etype]
    return etype


def rename_par(par_name):
    name_replacement = {
        'kick': 'angle'
    }

    if par_name in name_replacement: return name_replacement[par_name]
    return par_name


def get_par(par_list, par_name):
    for p in par_list:
        n, v = p.split('=')
        n = n.strip()
        v = v.strip()
        if n == par_name:
            return v
    return '0'


def expand_element(element_list, etype, params):
    exists_def = True
    while exists_def:
        try:
            new_def = element_list[etype]
            etype = new_def[0]
            # child parameters precede parent and are returned first from get_par
            params = params + new_def[1]
        except:
            exists_def = False

        return etype, params


def parameter_str(etype, par_list):
    if etype in ['marker', 'rcollimator', 'ecollimator', 'sequence']: return ''

    txt = ''
    par_names = []
    for p in par_list:
        n, v = p.split('=')
        n = n.strip()
        v = v.strip()
        if n not in par_names: txt = txt + rename_par(n) + '=' + v + ','
        par_names.append(n)

    return txt[:-1]


import time


def convert_madx_seq(fname, manual_defs=''):
    txt = ''
    # first strip comments to simplify multiline parsing
    lines = open(fname).read().lower().split('\n')
    for l in lines:
        l = l.strip()
        if l.find('!') >= 0: l = l[:l.find('!')]
        if l.find('//') >= 0: l = l[:l.find('//')]
        if len(l) > 0: txt = txt + l + '\n'

    lines = txt.split(';')

    txt = '#autogenerated on {} \nfrom ocelot import *\n'.format(time.strftime('%Y/%m/%d %H:%M:%S'))
    txt = txt + manual_defs

    pos = []
    element_list = {}

    for l in lines:
        l = l.strip().replace('\n', '')
        l = l.replace(':=', '=')
        if ':' in l:  # element def
            # print '!element def', l
            name, defn, = l.split(':')
            defn = defn.split(',')
            etype, params, = defn[0], defn[1:]
            name = name.strip()
            etype = etype.strip()
            if etype not in element_list:
                # print etype, 'not in element list'
                # print '!Defn: {} Basic class: {}'.format(name, etype)
                element_list[name] = (etype, params)
            else:
                etype, params = expand_element(element_list, etype, params)
                # print '!Child Defn: {} Basic class: {}'.format(name, etype)
                element_list[name] = (etype, params)

        elif 'at' in l:  # placement
            l = l.replace(',', '')
            l = l.replace('at =', 'at=')
            toks = l.split('at=')
            # print toks
            ename = toks[0].strip()
            par_val = get_par(element_list[ename][1], 'l')
            # print 'par_val = <{}>'.format(par_val)
            l = eval(par_val)
            pos.append((ename, str(eval(toks[1])), l))
        elif '=' in l:  # variables
            txt = txt + l + '\n'
            try:
                exec(l)
            except:
                print ('WARNING: unable to parse', l)

    for name in element_list.keys():
        etype, params = element_list[name]
        txt = txt + name + ' = ' + rename_type(etype) + '(' + parameter_str(etype, params) + ')\n'

    txt = txt + 'ring=('

    last_right_edge_s = 0.0
    for p in pos:
        l = p[2]
        s = eval(p[1])
        gap = s - l / 2.0 - last_right_edge_s
        last_right_edge_s = s + l / 2.0
        # txt = txt + p[0] + ' at ' + str(s) + ' l=' + str(l) + ' gap=' + str(gap) + '\n'
        if abs(gap) > 1.e-9:
            txt = txt + 'Drift(l=' + str(gap) + '),'
        txt = txt + p[0]
        txt = txt + ',\n'

    txt = txt + 'Marker() )'

    return txt


import re
def madx_input(s1):
    '''
    s1 os the ocelot inpu file as text string
    returns madx input as string    
    this is a template incorporating rules which work for PetraIV lattice
    
    '''
    s1 = re.sub(r"#", "!", s1)
    s1 = re.sub(r"(from.*import.*)", r"!\1 removed", s1)
    s1 = re.sub(r"=\s*(Quadrupole|Drift|SBend|Bend|RBend|Sextupole|Octupole)(\()(.*)(\))", r": \1, \3", s1)
    s1 = re.sub(r"=\s*(Cavity)(\()(l=[^,]*)(.*)(\))", r": Drift, \3", s1)
    s1 = re.sub(r"=\s*(Marker|Hcor|Monitor)(\()(.*)(\))", r": \1", s1)

    s1 = re.sub(r"(=)\s*(\((.|\n)*\))", r": line = \2", s1)
    s1 = re.sub(r"(=)\s*(\(.*\))", r": line = \2", s1)
    
    s1 = re.sub(r",\s*el_id\s*=\s*\".*\"", "", s1)
    s1 = re.sub(r",\s*el_id\s*=\s*\'.*\'", "", s1)
    s1 = re.sub(r"(\S+)\s*\n", r"\1;\n", s1)
    s1 = re.sub(r",\s*;", r";", s1)
    s1 = re.sub(r"\\;", "", s1) # multiline statements should have \ as line break
        
    s1 = re.sub(r"\.l", r"->l", s1)
    s1 = re.sub(r"\.k1", r"->k1", s1)

    s1 = re.sub(r"([\s,])(\S+)\*(\d+)([\s,])", r"\1\3*\2\4", s1) # number of repetitions first in madx 
    s1 = re.sub(r"(\(.+\))\*(\d+)", r"\2*\1", s1) # number of repetitions first in madx
    
    
    s1 = re.sub(r"(\w+)\[::-1\]", r"-\1", s1) # reflection
    
    s1 = re.sub(r"(qs_.*)(k1)(.*);", r"\1k1s\3;", s1) # change to skew quads based on naming convention 
    
    
    txt = '!autogenerated on {} \n'.format(time.strftime('%Y/%m/%d %H:%M:%S')) 
    txt += 'option, echo, info, warn;\n'
    txt += 'Hcor: HKicker;\n'
    txt += s1
    return txt


