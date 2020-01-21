#------------------------------------------------------------#
# This file is distributed as part of the Wannier19 code     #
# under the terms of the GNU General Public License. See the #
# file `LICENSE' in the root directory of the Wannier19      #
# distribution, or http://www.gnu.org/copyleft/gpl.txt       #
#                                                            #
# The Wannier19 code is hosted on GitHub:                    #
# https://github.com/stepan-tsirkin/wannier19                #
#                     written by                             #
#           Stepan Tsirkin, University ofZurich              #
#                                                            #
#------------------------------------------------------------#


import numpy as np
import sys
from . import __berry
from collections import Iterable, defaultdict
from . import __result as result
from time import time
from .__utility import alpha_A,beta_A

def __spin(data,degen):
    return [ [S[ib1:ib2,ib1:ib2] for ib1,ib2 in deg] for S,deg in zip(data.SSUU_K,degen)]

def __vel(data,degen):
    return [ [S[ib1:ib2,ib1:ib2] for ib1,ib2 in deg] for S,deg in zip(data.delHHUU_K,degen)]


##  so far it is Abelian!
def __curv(data):
    return data.Berry_nonabelian


def __morb(data):
    return data.Morb_nonabelian

def __morb_old(data,degen):
    CC=data.CCUU_K
    OO=data.OOmegaUU_K
    AA=data.AAUU_K
    dHH=data.delHHUU_K
    EE=data.E_K
    morb_klist=[]
    for C,O,A,dH,E,deg in zip(CC,OO,AA,dHH,EE,degen):
        morb_blist=[]
        for ib1,ib2 in deg:
            Ebar=np.mean(E[ib1:ib2])
            dH1=np.hstack( (dH[ib1:ib2,:ib1,:],dH[ib1:ib2,ib2:,:] ) )
            A1=np.hstack( (A[ib1:ib2,:ib1,:],A[ib1:ib2,ib2:,:] ) )
            invE=1./(np.hstack( (E[:ib1],E[ib2:]) ) - Ebar)
            M= np.einsum("mla,l,nla->mna", dH1[:,:,alpha_A],invE,dH1[:,:,beta_A].conj() )
            M+=1j*( - np.einsum("mla,nla->mna",A1[:,:,alpha_A],dH1[:,:,beta_A].conj() ) 
                      + np.einsum("mla,nla->mna",dH1[:,:,alpha_A],A1[:,:,beta_A].conj() ) ) 
            M+=M.conj().transpose((1,0,2))
            M+=C[ib1:ib2,ib1:ib2]-O[ib1:ib2,ib1:ib2]*Ebar
            morb_blist.append(M)
        morb_klist.append(morb_blist)
    return morb_klist


__dimensions=defaultdict(lambda : 1)

#quantities that should be odd under TRS and inversion
TRodd  = set(['spin','morb','vel','curv'])
INVodd = set(['vel'])


def spin(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['spin'],degen_thresh=degen_thresh)



def spinvel(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['spin','vel'],degen_thresh=degen_thresh)

def curvvel(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['curv','vel'],degen_thresh=degen_thresh)

def curvmorb(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['curv','morb'],degen_thresh=degen_thresh)


def velvel(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['vel','vel'],degen_thresh=degen_thresh)


def morbvel(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['morb','vel'],degen_thresh=degen_thresh)


def spinspin(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['spin','spin'],degen_thresh=degen_thresh)


def curv_tot(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['curv'],degen_thresh=degen_thresh,mode='fermi-sea')


def ahc(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['curv'],degen_thresh=degen_thresh,mode='fermi-sea',factor=__berry.fac_ahc)


def morb_tot(data,Efermi,degen_thresh):
    return nonabelian_general(data,Efermi,['morb'],degen_thresh=degen_thresh,mode='fermi-sea',factor=__berry.fac_morb)



def nonabelian_general(data,Efermi,quantities,subscripts=None,degen_thresh=1e-5,mode='fermi-surface',factor=1):
    E_K=data.E_K

    dE=Efermi[1]-Efermi[0]
    Emin=Efermi[0]-dE/2
    Emax=Efermi[-1]+dE/2
#    include_lower=(mode=='fermi-sea')
    data.set_degen(Emin=Emin,Emax=Emax,degen_thresh=degen_thresh)

    variables=vars(sys.modules[__name__])
    M=[variables["__"+Q](data) for Q in quantities]


    if subscripts is None:
        ind_cart="abcdefghijk"
        left=[]
        right=""
        for Q in quantities:
            d=__dimensions[Q]
            left.append(ind_cart[:d])
            right+=ind_cart[:d]
            ind_cart=ind_cart[d:]
    else:
        left,right=subscripts.split("->")
        left=left.split(",")
        for Q,l,q in zip(quantities,left,quantities):
            d=__dimensions[Q]
            if d!=len(left):
                raise RuntimeError("The number of subscripts in '{}' does not correspond to dimention '{}' of quantity '{}' ".format(l,d,q))


    ind_bands="lmnopqrstuvwxyz"[:len(quantities)]
    ind_bands+=ind_bands[0]
    einleft=[]
    for l in left:
        einleft.append(ind_bands[:2]+l)
        ind_bands=ind_bands[1:]

    einline=",".join(einleft)+"->"+right
#    print ("using line '{}' for einsum".format(einline))


    res=np.zeros(  (len(Efermi),)+(3,)*len(right)  )

    if mode=='fermi-surface':
      for ik in range(data.NKFFT_tot):
        indE=np.array(np.round( (data.E_K_degen[ik]-Efermi[0])/dE ),dtype=int )
        indEtrue= (0<=indE)*(indE<len(Efermi))
        for ib,ie,it  in zip(range(len(indE)),indE,indEtrue):
            if it:
#                print ("quantities: ",quantities,einline,[m[ik][ib] for m in M])
                res[ie]+=np.einsum(einline,*(m[ik][ib] for m in M)).real
      res=res/dE
    elif mode=='fermi-sea':
      for ik in range(data.NKFFT_tot):
        indE=np.array(np.round( (data.E_K_degen[ik]-Efermi[0])/dE ),dtype=int )
        indEtrue= (0<=indE)*(indE<len(Efermi))
        for ib,eav  in zip(range(len(indE)),data.E_K_degen[ik]):
            if eav<Emax:
                 res[eav<Efermi]+=np.einsum(einline,*(m[ik][ib] for m in M)).real
    else:
      raise ValueError('unknown mode in non-abelian: <{}>'.format(mode))

    return result.EnergyResult(Efermi,res*(factor/(data.NKFFT_tot*data.cell_volume)),TRodd=odd_prod_TR(quantities),Iodd=odd_prod_INV(quantities))



def odd_prod_TR(quant):
   return odd_prod(quant,TRodd)

def odd_prod_INV(quant):
   return odd_prod(quant,INVodd)


def odd_prod(quant,odd):
    return  bool(sum( (q in odd) for q in quant )%2)
