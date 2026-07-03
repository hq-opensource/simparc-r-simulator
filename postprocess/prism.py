"""
La méthode PRISM (PRInceton Scorekeeping Method [1]) est basée sur la régression linéaire par segment, qui est une méthode de régression linéaire qui divise les données en segments et ajuste un modèle linéaire à chaque segment. 

   |      \
   |     k0\
 y0|........\
   |        /\
   |     k0/ .\k1       /
   |      /  . \       /k2
 y1|............\_____/
   |         .  .    .
   ----------.--.----.------------------>   
             x0 x1   x2

[1] M. F. Fels, «PRISM: An Introduction,» Eenrgy and Building, 1986
"""
from os import listdir
from os.path import isdir, isfile, join
import numpy as np
import pandas as pd
import datetime as dt
import math
from scipy import optimize, stats, linalg
#import statsmodels.formula.api as sm
import statsmodels.api as sm
import copy
import numpy as np

class Prism():
    """
    A class representing a Prism object.
    
    Attributes:
    - QuotikWh: A list of hourly energy consumption values in kilowatt-hours (kWh).
    - QuotiTemp: A list of hourly temperature values.
    - Attributs: A dictionary of additional attributes.
    """
    def __init__(self,QuotikWh,QuotiTemp,Attributs={}):
        """
        Initializes a Prism object.
        
        Parameters:
        - QuotikWh: A list of hourly energy consumption values in kilowatt-hours (kWh).
        - QuotiTemp: A list of hourly temperature values.
        - Attributs: A dictionary of additional attributes.
        """
        self.P_4seg=True # False = on ne veut pas de prism 4 segments.

        self.x=np.array(QuotiTemp)#np.array(QuotiTemp)/24 #kwh to kw
        self.y=np.array(QuotikWh)/24 #24 #kwh to kw
        
        self.Attributs=Attributs #
        

    def trace(self, Show = True, Save = False, SavePathName =None): #inutile pour prod. utile en dev python
        """
        Generates a figure of the calculated prism.
        
        Parameters:
        - Show: A boolean indicating whether to display the figure.
        - Save: A boolean indicating whether to save the figure.
        - SavePathName: The path and name of the file to save the figure.
        """
    
        x = self.x
        y = self.y
        xd = np.linspace(x.min(), x.max(), 1000)
        p = self.p

        IC_LOW = 0.0
        IC_HIGH = 0.0

        # Trace le modele retenu
        if(self.model=='2ch'):
#            
            # Calcul l'erreur de prediction
            lower = []
            upper = []
            xxd = []
            if (len(x[x<p[1]]) >3 and len(x[(x>=p[1])]) > 2): # 2 segments chauffage
                # Segment 1 : chauffage
                n = len(x[x<p[1]])
                if(n>3):
                    SE1 = math.sqrt(np.sum(np.square(y[x<p[1]]-self.piecewise_linear_2seg_ch(x[x<p[1]], *p)))/(n-2-1))
                    SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd<p[1]]-np.mean(xd[xd<p[1]]))/(np.sum(np.square(xd[xd<p[1]]-np.mean(xd[xd<p[1]])))))
                    student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                    lower = lower + ((self.piecewise_linear_2seg_ch(xd[xd<p[1]], *p)-student*SP1).tolist())
                    upper = upper + ((self.piecewise_linear_2seg_ch(xd[xd<p[1]], *p)+student*SP1).tolist())
                    IC_LOW = np.mean(lower);
                    IC_HIGH = np.mean(upper);
                    
                    xxd = xxd + xd[xd<p[1]].tolist()
                    
                # Segment 2 : base
                n = len(x[(x>=p[1])])
                if(n>2): 
                    SE1 = math.sqrt(np.sum(np.square(y[(x>=p[1])]-self.piecewise_linear_2seg_ch(x[(x>=p[1])], *p)))/(n-1-1))
                    SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[(xd>=p[1])]-np.mean(xd[(xd>=p[1])]))/(np.sum(np.square(xd[(xd>=p[1])]-np.mean(xd[(xd>=p[1])])))))
                    student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-1)
                    lower = lower + ((self.piecewise_linear_2seg_ch(xd[(xd>=p[1])], *p)-student*SP1).tolist())
                    upper = upper + ((self.piecewise_linear_2seg_ch(xd[(xd>=p[1])], *p)+student*SP1).tolist())
                    xxd = xxd + xd[xd>=p[1]].tolist()

            else: # un seul segment
                # Segment 1 : chauffage
                n = len(x[x<99])
                SE1 = math.sqrt(np.sum(np.square(y[x<99]-self.piecewise_linear_2seg_ch(x[x<99], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd<99]-np.mean(xd[xd<99]))/(np.sum(np.square(xd[xd<p[1]]-np.mean(xd[xd<99])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_2seg_ch(xd[xd<99], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_2seg_ch(xd[xd<99], *p)+student*SP1).tolist())
                xxd = xxd + xd[xd<99].tolist()
        if(self.model=='2cl'):
            # Calcul l'erreur de prediction
            lower = []
            upper = []
            xxd = []
            # Segment 1 :Basse
            n = len(x[x<p[2]])
            if(n>3): 
                SE1 = math.sqrt(np.sum(np.square(y[x<p[2]]-self.piecewise_linear_2seg_cl(x[x<p[2]], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd<p[2]]-np.mean(xd[xd<p[2]]))/(np.sum(np.square(xd[xd<p[2]]-np.mean(xd[xd<p[2]])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_2seg_cl(xd[xd<p[2]], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_2seg_cl(xd[xd<p[2]], *p)+student*SP1).tolist())
                xxd = xxd + xd[xd<p[2]].tolist()
            # Segment 2 : climatisation
            n = len(x[(x>=p[2])])
            if(n>2):
                SE1 = math.sqrt(np.sum(np.square(y[(x>=p[2])]-self.piecewise_linear_2seg_cl(x[(x>=p[2])], *p)))/(n-1-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[(xd>=p[2])]-np.mean(xd[(xd>=p[2])]))/(np.sum(np.square(xd[(xd>=p[2])]-np.mean(xd[(xd>=p[2])])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-1)
                lower = lower + ((self.piecewise_linear_2seg_cl(xd[(xd>=p[2])], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_2seg_cl(xd[(xd>=p[2])], *p)+student*SP1).tolist())
                xxd = xxd + xd[xd>=p[2]].tolist()
                
        if(self.model=='3sg'):
            # Calcul de l'erreur de prediction à 95%
            lower = []
            upper = []
            xxd = []
            # Segment 1 : Chauffage
            n = len(x[x<p[1]])
            if(n>3):
                SE1 = math.sqrt(np.sum(np.square(y[x<p[1]]-self.piecewise_linear_3seg(x[x<p[1]], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd<p[1]]-np.mean(xd[xd<p[1]]))/(np.sum(np.square(xd[xd<p[1]]-np.mean(xd[xd<p[1]])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_3seg(xd[xd<p[1]], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_3seg(xd[xd<p[1]], *p)+student*SP1).tolist())
                IC_LOW = np.mean(lower);
                IC_HIGH = np.mean(upper);
                
                xxd = xxd + xd[xd<p[1]].tolist()
            # Segment 2 : Base
            if(p[1]<p[2]):
                n = len(x[(x>p[1]) & (x<p[2])])
                if(n>2):
                    SE1 = math.sqrt(np.sum(np.square(y[(x>p[1]) & (x<p[2])]-self.piecewise_linear_3seg(x[(x>p[1]) & (x<p[2])], *p)))/(n-1-1))
                    SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[(xd>=p[1]) & (xd<p[2])]-np.mean(xd[(xd>=p[1]) & (xd<p[2])]))/(np.sum(np.square(xd[(xd>=p[1]) & (xd<p[2])]-np.mean(xd[(xd>=p[1]) & (xd<p[2])])))))
                    student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-1)
                    lower = lower + ((self.piecewise_linear_3seg(xd[(xd>=p[1]) & (xd<p[2])], *p)-student*SP1).tolist())
                    upper = upper + ((self.piecewise_linear_3seg(xd[(xd>=p[1]) & (xd<p[2])], *p)+student*SP1).tolist())
                    xxd = xxd + xd[(xd>=p[1]) & (xd<p[2])].tolist()

            # Segment 2 : Climatisation
            n = len(x[x>p[2]])
            if(n>3):
                SE1 = math.sqrt(np.sum(np.square(y[x>p[2]]-self.piecewise_linear_3seg(x[x>p[2]], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd>=p[2]]-np.mean(xd[xd>=p[2]]))/(np.sum(np.square(xd[xd>=p[2]]-np.mean(xd[xd>=p[2]])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_3seg(xd[xd>=p[2]], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_3seg(xd[xd>=p[2]], *p)+student*SP1).tolist())
                xxd = xxd + xd[xd>=p[2]].tolist()

        if(self.model=='4sg'):
            # Calcul de l'erreur de prediction à 95%
            lower = []
            upper = []
            xxd = []
            # Segment 1
            n = len(x[x<p[0]])
            if(n>3):
                SE1 = math.sqrt(np.sum(np.square(y[x<p[0]]-self.piecewise_linear_4seg(x[x<p[0]], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd<p[0]]-np.mean(xd[xd<p[0]]))/(np.sum(np.square(xd[xd<p[0]]-np.mean(xd[xd<p[0]])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_4seg(xd[xd<p[0]], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_4seg(xd[xd<p[0]], *p)+student*SP1).tolist())
                xxd = xxd + xd[xd<p[0]].tolist()
                
            # Segment 2
            n = len(x[(x>p[0]) & (x<p[1])])
            if(n>3):
                SE1 = math.sqrt(np.sum(np.square(y[(x>=p[0]) & (x<p[1])]-self.piecewise_linear_4seg(x[(x>=p[0]) & (x<p[1])], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[(xd>=p[0]) & (xd<p[1])]-np.mean(xd[(xd>=p[0]) & (xd<p[1])]))/(np.sum(np.square(xd[(xd>=p[0]) & (xd<p[1])]-np.mean(xd[(xd>=p[0]) & (xd<p[1])])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_4seg(xd[(xd>=p[0]) & (xd<p[1])], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_4seg(xd[(xd>=p[0]) & (xd<p[1])], *p)+student*SP1).tolist())
                xxd = xxd + xd[(xd>=p[0]) & (xd<p[1])].tolist()

            IC_LOW = np.mean(lower)
            IC_HIGH = np.mean(upper)
            # Segment 3
            n = len(x[(x>p[1]) & (x<p[2])])
            if(n>2):
                SE1 = math.sqrt(np.sum(np.square(y[(x>p[1]) & (x<p[2])]-self.piecewise_linear_4seg(x[(x>p[1]) & (x<p[2])], *p)))/(n-1-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[(xd>=p[1]) & (xd<p[2])]-np.mean(xd[(xd>=p[1]) & (xd<p[2])]))/(np.sum(np.square(xd[(xd>=p[1]) & (xd<p[2])]-np.mean(xd[(xd>=p[1]) & (xd<p[2])])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-1)
                lower = lower + ((self.piecewise_linear_4seg(xd[(xd>=p[1]) & (xd<p[2])], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_4seg(xd[(xd>=p[1]) & (xd<p[2])], *p)+student*SP1).tolist())
                xxd = xxd + xd[(xd>=p[1]) & (xd<p[2])].tolist()

            # Segment 4
            n = len(x[x>p[2]])
            if(n>3):
                SE1 = math.sqrt(np.sum(np.square(y[x>p[2]]-self.piecewise_linear_4seg(x[x>p[2]], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd>=p[2]]-np.mean(xd[xd>=p[2]]))/(np.sum(np.square(xd[xd>=p[2]]-np.mean(xd[xd>=p[2]])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_4seg(xd[xd>=p[2]], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_4seg(xd[xd>=p[2]], *p)+student*SP1).tolist())
                xxd = xxd + xd[xd>=p[2]].tolist()

        if(self.model=='3be'):
            # Calcul de l'erreur de prediction à 95%
            lower = []
            upper = []
            xxd = []
            
            # Segment 1
            n = len(x[x<p[0]])
            if(n>3):
                SE1 = math.sqrt(np.sum(np.square(y[x<p[0]]-self.piecewise_linear_3be(x[x<p[0]], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd<p[0]]-np.mean(xd[xd<p[0]]))/(np.sum(np.square(xd[xd<p[0]]-np.mean(xd[xd<p[0]])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_3be(xd[xd<p[0]], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_3be(xd[xd<p[0]], *p)+student*SP1).tolist())
                xxd = xxd + xd[xd<p[0]].tolist()
                
            # Segment 2
            n = len(x[(x>p[0]) & (x<p[1])])
            if(n>3):
                SE1 = math.sqrt(np.sum(np.square(y[(x>=p[0]) & (x<p[1])]-self.piecewise_linear_3be(x[(x>=p[0]) & (x<p[1])], *p)))/(n-2-1))
                SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[(xd>=p[0]) & (xd<p[1])]-np.mean(xd[(xd>=p[0]) & (xd<p[1])]))/(np.sum(np.square(xd[(xd>=p[0]) & (xd<p[1])]-np.mean(xd[(xd>=p[0]) & (xd<p[1])])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-2)
                lower = lower + ((self.piecewise_linear_3be(xd[(xd>=p[0]) & (xd<p[1])], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_3be(xd[(xd>=p[0]) & (xd<p[1])], *p)+student*SP1).tolist())
                xxd = xxd + xd[(xd>=p[0]) & (xd<p[1])].tolist()

            IC_LOW = np.mean(lower)
            IC_HIGH = np.mean(upper)
            # Segment 3
            n = len(x[(x>p[1])])# & (x<p[2])])
            if(n>2):
                SE1 = math.sqrt(np.sum(np.square(y[x>p[1]]-self.piecewise_linear_3seg(x[x>p[1]], *p)))/(n-2-1))
                SP1 = SP1 = SE1*np.sqrt(1.0+1.0/n+np.square(xd[xd>=p[1]]-np.mean(xd[xd>=p[1]]))/(np.sum(np.square(xd[xd>=p[1]]-np.mean(xd[xd>=p[1]])))))
                student = stats.t.ppf(1.0-0.5*(1.0-0.95),n-1)
                lower = lower + ((self.piecewise_linear_3be(xd[(xd>=p[1]) ], *p)-student*SP1).tolist())
                upper = upper + ((self.piecewise_linear_3be(xd[(xd>=p[1]) ], *p)+student*SP1).tolist())
                xxd = xxd + xd[(xd>=p[1])].tolist()

        self.lower = lower
        self.upper = upper
        self.xd = xxd
        # Turn interactive plotting off
        plt.ioff()
        
        fig, ax1 = plt.subplots(1,1,figsize=(15, 7.5))#plt.figure()
        plt.plot(self.x, self.y, "bo", alpha=0.2)

        # Trace le model retenu
        if(self.model=='2ch'): plt.plot(self.xd, self.piecewise_linear_2seg_ch(self.xd, *self.p), 'k-',linewidth=3)
        if(self.model=='2cl'): plt.plot(self.xd, self.piecewise_linear_2seg_cl(self.xd, *self.p), 'k-',linewidth=3)
        if(self.model=='3sg'): plt.plot(self.xd, self.piecewise_linear_3seg(self.xd, *self.p), 'k-',linewidth=3)
        if(self.model=='4sg'): plt.plot(self.xd, self.piecewise_linear_4seg(self.xd, *self.p), 'k-',linewidth=3)
        if(self.model=='3be'): plt.plot(self.xd, self.piecewise_linear_3be(self.xd, *self.p), 'k-',linewidth=3)

        plt.plot(self.xd, self.lower, 'k--',linewidth=2)
        plt.plot(self.xd, self.upper, 'k--',linewidth=2)

        plt.grid()
        plt.xlabel(u'Température [°C]')
        plt.ylabel(u'Puissance moyenne quotidienne [kW]')
        plt.legend([u'Données',u'Modèle',u'IC @ 95%'])
        plt.title("PRISM")
        plt.tight_layout()

        self.fig = plt.gcf()

        if (Save == True):
            if (SavePathName !=None):
                plt.savefig(SavePathName)

        # Display all "open" (non-closed) figures
        if (Show ==True):
            plt.show()
        else:
            plt.close(fig)
    ###########################################################################
    #Méthode pour gérer les différents type de PRISM
    # 1,2,3,4 segments
    # La méthode unique paramtriseable n'est pas encore implantée et robuste
    def piecewise_linear_4seg(self,x, x0, x1, x2, y0, y1, k0, k1, k2):
        """
        Compute the piecewise linear function with 4 segments.

        Parameters:
        - x: Input array of x-values.
        - x0, x1, x2: Breakpoints for the piecewise function.
        - y0, y1: y-values at the breakpoints.
        - k0, k1, k2: Slopes of the linear segments.

        Returns:
        - Array of y-values corresponding to the input x-values.

        Notes:
        - The function computes the piecewise linear function with 4 segments, where the slope changes at the breakpoints.
        - The function uses numpy's piecewise function to compute the output array.

        Example usage:
        >>> x = np.linspace(0, 10, 100)
        >>> y = piecewise_linear_4seg(x, 2, 4, 8, 0, 5, 1, -1, 2)
        """

        k1 = (y0-y1)/(x0-x1)
        if(x1>x2):
            tempo = (k1*x1-k2*x2)/(k1-k2)
            x1, x2 =tempo, tempo
            y1 = k1*(x1-x0)+y0
        if(k1>0):
            k1=0.0
        if(k2<0):
            k2=0.0
        return np.piecewise(x, [x <= x0, ((x > x0) & (x <= x1)), x >= x2], \
        [lambda x:k0*(x-x0) + y0, \
        lambda x:(y0-y1)*(x-x1)/(x0-x1) + y1, \
        lambda x:k2*(x-x2) + y1, \
        lambda x:y1])

    def piecewise_linear_3seg(self,x, x0, x1, x2, y0, y1, k0, k1, k2):
        """
        Compute the piecewise linear function with 3 segments.

        Parameters:
        - x: Input array of x-values.
        - x0, x1, x2: Breakpoints for the piecewise function.
        - y0, y1: y-values at the breakpoints.
        - k0, k1, k2: Slopes of the linear segments.

        Returns:
        - Array of y-values corresponding to the input x-values.

        Notes:
        - The function computes the piecewise linear function with 3 segments, where the slope changes at the breakpoints.
        - The function uses numpy's piecewise function to compute the output array.

        Example usage:
        >>> x = np.linspace(0, 10, 100)
        >>> y = piecewise_linear_3seg(x, 2, 4, 8, 0, 5, 1, -1, 2)
        """

        if(x1>x2):
            tempo = (k1*x1-k2*x2)/(k1-k2)
            x1, x2 =tempo, tempo
            y1 = k1*(x1-x0)+y0
        return np.piecewise(x, [x <= x1, x >= x2], \
        [lambda x:k1*(x-x1) + y1, \
        lambda x:k2*(x-x2) + y1, \
        lambda x:y1])

    def piecewise_linear_2seg_ch(self,x, x0, x1, x2, y0, y1, k0, k1, k2):
        """
        Compute the piecewise linear function with 2 segments with heating.

        Parameters:
        - x: Input array of x-values.
        - x0, x1, x2: Breakpoints for the piecewise function.
        - y0, y1: y-values at the breakpoints.
        - k0, k1, k2: Slopes of the linear segments.

        Returns:
        - Array of y-values corresponding to the input x-values.

        Notes:
        - The function computes the piecewise linear function with 2 segments with heating, where the slope changes at the breakpoints.
        - The function uses numpy's piecewise function to compute the output array.

        Example usage:
        >>> x = np.linspace(0, 10, 100)
        >>> y = piecewise_linear_2ch(x, 2, 4, 8, 0, 5, 1, -1, 2)
        """
        if(k1>0):
            k1=0.0
        return np.piecewise(x, [x <= x1], \
        [lambda x:k1*(x-x1) + y1, \
        lambda x:y1])

    def piecewise_linear_2seg_cl(self,x, x0, x1, x2, y0, y1, k0, k1, k2):
        """
        Compute the piecewise linear function with 2 segments with cooling.

        Parameters:
        - x: Input array of x-values.
        - x0, x1, x2: Breakpoints for the piecewise function.
        - y0, y1: y-values at the breakpoints.
        - k0, k1, k2: Slopes of the linear segments.

        Returns:
        - Array of y-values corresponding to the input x-values.

        Notes:
        - The function computes the piecewise linear function with 2 segments with cooling, where the slope changes at the breakpoints.
        - The function uses numpy's piecewise function to compute the output array.

        Example usage:
        >>> x = np.linspace(0, 10, 100)
        >>> y = piecewise_linear_2cl(x, 2, 4, 8, 0, 5, 1, -1, 2)
        """
                
        if(k2<0):
            k2=0.0
        return np.piecewise(x, [x >= x2],
        [lambda x:k2*(x-x2) + y1, \
        lambda x:y1])

    def piecewise_linear_3be(self,x, x0, x1, x2, y0, y1, k0, k1, k2):
        """
        Compute the piecewise linear function with 3 segments (dual-energy) without cooling.

        Parameters:
        - x: Input array of x-values.
        - x0, x1, x2: Breakpoints for the piecewise function.
        - y0, y1: y-values at the breakpoints.
        - k0, k1, k2: Slopes of the linear segments.

        Returns:
        - Array of y-values corresponding to the input x-values.

        Notes:
        - The function computes the piecewise linear function with 3 segments (dual-energy) without cooling, where the slope changes at the breakpoints.
        - The function uses numpy's piecewise function to compute the output array.

        Example usage:
        >>> x = np.linspace(0, 10, 100)
        >>> y = piecewise_linear_3be(x, 2, 4, 8, 0, 5, 1, -1, 2)
        """
        
        if(k1>0):
            k1=0.0
        
        return np.piecewise(x, [x <= x0, ((x > x0) & (x <= x1))], \
        [lambda x:k0*(x-x0) + y0, \
        lambda x:(y0-y1)*(x-x1)/(x0-x1) + y1, \
        lambda x:y1])

    def Test_Fisher(self, SSE, num_params, nb_point, confiance):
        """
        Perform a Fisher statistical test to select the most significant number of segments among those that have worked.

        Parameters:
        - SSE (list): List of sum of squared errors for each segment.
        - num_params (list): List of the number of parameters for each segment.
        - nb_point (int): Number of data points.
        - confiance (float): Confidence level for the test.

        Returns:
        - numpy.ndarray: Boolean array indicating which segments are more significant based on the Fisher test.
        """
        dim = len(SSE)
        F = np.zeros((dim-1,dim-1))
        Fc = np.zeros((dim-1,dim-1))
        for i in range(dim-1):
            for j in range(i+1,dim):
                if SSE[j] !=np.inf:
                    if (nb_point<=(num_params[j]-1)):
                        F[i,j-1] = (SSE[i]-SSE[j])/(num_params[j]-num_params[i]+1e-20)/(SSE[j]/(1e-5))                   
                    else:
                        F[i,j-1] = (SSE[i]-SSE[j])/(num_params[j]-num_params[i]+1e-20)/(SSE[j]/(nb_point-num_params[j]+1))
                Fc[i,j-1] = stats.f.pdf(confiance, num_params[j]-num_params[i], nb_point-num_params[j]+1)
                #print(str(i),' ',str(j-1))
        return F > Fc
    
    def Init_param_prism(self,x0=-10.0,x1=10.0,x2=20.0):
        """
        Method to choose the initial parameters to facilitate the convergence of optimization.

        Parameters:
        - x0 (float): Initial value for x0 parameter (default: -10.0)
        - x1 (float): Initial value for x1 parameter (default: 10.0)
        - x2 (float): Initial value for x2 parameter (default: 20.0)

        Returns:
        - pini (list): List of initial parameters [x0, x1, x2, y0, y1, k0, k1, k2]
        
        illustration
           |      \
           |     k0\
         y0|........\
           |        /\
           |     k0/ .\k1       /
           |      /  . \       /k2
         y1|............\_____/
           |         .  .    .
        #   ----------.--.----.------------------>   
        #             x0 x1   x2
        
        """

        #parametres initiaux
        #               x0,   x1,   x2   y0  y1   k0    k1    k2
        lst_defaut = [-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 1.0]          
        
        x=self.x
        y=self.y
        
        x0ini = x0#-10
        x1ini = x1#10
        x2ini = x2#20
        
        try:
            y0ini = np.mean(y[np.where((x>(x0ini-5)) & (x<(x0ini+5)))])
        except:
            y0ini = lst_defaut[3]#72#kwh/j
        
        
        #estimation pente de chauffage k1
        try:
            y1ini = np.mean(y[np.where((x>(x1ini)) & (x<(x2ini)))])
        except:
            y1ini = lst_defaut[4]#24#kwh/j
            
        try:
            resultCH = sm.OLS(y[np.where((x>(x0ini)) & (x<(x1ini)))],
                              sm.tools.add_constant(x[np.where((x>(x0ini)) & (x<(x1ini)))])).fit()
            k1ini = resultCH.params[1]
            b1ini = resultCH.params[0]

        except:
            k1ini=1
            
            
        if (k1ini<=-50) | (k1ini>0):
            if x1ini!=x0ini:
                k1ini = (y1ini-y0ini)/(x1ini-x0ini) #dt=10°c
                b1ini = y1ini-k1ini*x1ini
            else:
                k1ini=lst_defaut[6]
                b1ini = y1ini-k1ini*x1ini
        
        #estimation pente de chauffage k0
        try:
            y0temp = np.mean(y[np.where(x<x0ini)])
            x0temp = np.mean(x[np.where(x<x0ini)])
        except:
            y0temp = lst_defaut[3]#72#kwh/j 
            x0temp = -25
        try:
            resultCH0 = sm.OLS(y[np.where(x<x0ini)],
                               sm.tools.add_constant(x[np.where(x<x0ini)])).fit()
            k0ini = resultCH0.params[1]
            b0ini = resultCH0.params[0]
        except:
            k0ini=-1
            
        if (k0ini<=-50) | (k0ini>0):            
            if x0ini!=x0temp:
                k0ini = (y0ini-y0temp)/(x0ini-x0temp)
                b0ini = y0ini-k0ini*x0ini
            else:
                k0ini =lst_defaut[5] 
                b0ini = y0ini-k0ini*x0ini
        
        #estimation pente de clim
        try:
            y2temp = np.mean(y[np.where(x>x2ini)])
            x2temp = np.mean(x[np.where(x>x2ini)])  
        except:
            y2temp = lst_defaut[3]#72#kwh/j 
            x2temp = 25
        try:
            resultCL = sm.OLS(y[np.where(x>x2ini)],
                              sm.tools.add_constant(x[np.where(x>x2ini)])).fit()
            k2ini = resultCL.params[1]
            b2ini = resultCL.params[0]
        except:
            k2ini=-1
   
        if (k2ini>=20) | (k2ini<0):
            if x2temp!=x2ini:
                k2ini = (y2temp-y1ini)/(x2temp-x2ini)
                b2ini = y1ini-k2ini*x2ini
            else:
                k2ini=lst_defaut[7]
                b2ini = y1ini-k2ini*x2ini
    
            if k2ini<0:
                k2ini=lst_defaut[7]
                b2ini = y1ini-k2ini*x2ini
           
        #réévaluation des températures
        try:
            x0fin = (b1ini-b0ini)/(k0ini-k1ini)
        except:
            x0fin = x0ini

        try:
            x1fin = (y1ini-b1ini)/(k1ini)
        except:
            x1fin = x1ini

        try:
            x2fin = (b2ini-y1ini)/(-k2ini)
        except:
            x2fin = x2ini
        
        if ((x0fin<np.min(x)) | (x0fin>np.max(x))):
            x0fin=x0ini

        if ((x1fin<x0fin) | (x1fin>np.max(x))):
            x1fin=np.max([x1ini,x0fin])
            
        if ((x2fin<x1fin) | (x2fin>np.max(x))):
            x2fin=np.max([x1fin,x2ini])

        pini = [x0fin,x1fin,x2fin,y0ini,y1ini,k0ini,k1ini, k2ini]
        for item in range(len(pini)):
            if math.isnan(pini[item]):
                pini[item] = lst_defaut[item]
        
        return pini

    def get_param_ini_prism(self):
        """
        Returns the initial parameters for the Prism model.

        This method defines the initial parameters available for the Prism model.
        It calculates the error for each parameter configuration and selects the
        configuration with the lowest error.

        Returns:
            dict: A dictionary containing the initial parameter configuration with
                  the lowest error.
        """

#                              x0,   x1,   x2   y0  y1   k0    k1   k2
        dic_init_param={0:   [-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 1.0]}
        
        dic_init_param[10] = self.Init_param_prism(x0=-10,x1=-8,x2=20)#[-10.0, -8.0, 24.0, 72, ym, 2.4, -2.4, 1.0], #0 pente
        dic_init_param[11] = self.Init_param_prism(x0=-10,x1=10,x2=20)#1 pente ch +base
        dic_init_param[12] = self.Init_param_prism(x0=0,x1=10,x2=20)#1 pente ch +base
        dic_init_param[12] = self.Init_param_prism(x0=-10,x1=0,x2=15) #1 pente cl +base
        dic_init_param[13] = self.Init_param_prism(x0=-10,x1=10,x2=20) #3 seg ch+cl +base
        dic_init_param[14] = self.Init_param_prism(x0=-10,x1=10,x2=20) #4 seg comb+ch+cl +base
        dic_init_param[15] = self.Init_param_prism(x0=0,x1=10,x2=20) #4 seg elec+pacch+cl +base
        dic_init_param[16] = self.Init_param_prism(x0=-10,x1=10,x2=20) #3seg bienergie 20240514

        
        #choix de la meilleure config
        x=self.x
        y=self.y
        er={}
        er[0] =  np.sum(np.sum(np.square(y-self.piecewise_linear_3seg(x,*dic_init_param[0]))))
        er[10] = np.sum(np.sum(np.square(y-self.piecewise_linear_2seg_ch(x,*dic_init_param[10]))))
        er[11] = np.sum(np.sum(np.square(y-self.piecewise_linear_2seg_ch(x,*dic_init_param[11]))))
        er[12] = np.sum(np.sum(np.square(y-self.piecewise_linear_2seg_cl(x,*dic_init_param[12]))))
        er[13] = np.sum(np.sum(np.square(y-self.piecewise_linear_3seg(x,*dic_init_param[13]))))
        er[14] = np.sum(np.sum(np.square(y-self.piecewise_linear_3be(x,*dic_init_param[16]))))

        if self.P_4seg:
            er[14] = np.sum(np.sum(np.square(y-self.piecewise_linear_4seg(x,*dic_init_param[14]))))
            er[15] = np.sum(np.sum(np.square(y-self.piecewise_linear_4seg(x,*dic_init_param[15]))))
        
        pini = dic_init_param[0]
        er0 = er[0]
        self.Model_ini = str(0)
        #ite=0
        for item in er.keys():
            if er[item]<er0:
                pini = dic_init_param[item]
                er0 = er[item]
                self.Model_ini=str(item)
        #print(ite)
        return pini
        

    def SSE_CVRMSE_seg(self,Dyfy,x,y,p,Model):
        """
        Method to calculate the Sum of Squared Errors (SSE) and Coefficient of Variation of Root Mean Squared Error (CVRMSE)
        for the segments of the PRISM.

        Parameters:
        - Dyfy (array): Array of Errors.
        - x (array): Array of x-values.
        - y (array): Array of y-values.
        - p (list): List of parameters.
        - Model (str): Model type.

        Returns:
        - list: A list containing the SSE, CVRMSE, and number of points for each segment.
        """
        
        #Methode pour calculer le SSE et le CVRMSE des segments du PRISM
        
        if Model == '4sg':
            Tmin = [-9999,p[0],p[1],p[2]]
            Tmax = [p[0],p[1],p[2],9999]
            num_params = [3,4,3,3]
        #x0,   x1,   x2   y0  y1   k0    k1    k2
        #num_params[0] : x0,  y0, k0
        #num_params[1] : x0, x1, y1, k1
        #num_params[2] : x1, x2  y1
        #num_params[3] : x2,y1 k2
        
        elif Model == '3sg':
            Tmin = [-9999,-9999,p[1],p[2]]
            Tmax = [-9999,p[1],p[2],9999]
            num_params = [-9999,3,3,3]
        #x0,   x1,   x2   y0  y1   k0    k1    k2
        #num_params[0] : -
        #num_params[1] : x1, y1, k1
        #num_params[2] : x1, x2  y1
        #num_params[3] : x2,y1 k2
            
        elif Model == '2ch':
            Tmin = [-9999,-9999,p[1],9999]
            Tmax = [-9999,p[1],9999,9999]
            num_params = [-9999,3,2,-9999]
        #x0,   x1,   x2   y0  y1   k0    k1    k2
        #num_params[0] : -
        #num_params[1] : x1, y1, k1
        #num_params[2] : x1, y1
        #num_params[3] : -
        elif Model == '2cl':
            Tmin = [-9999,-9999,-9999,p[2]]
            Tmax = [-9999,-9999,p[2],9999]
            num_params = [-9999,-9999,2,3]
        #x0,   x1,   x2   y0  y1   k0    k1    k2
        #num_params[0] : -
        #num_params[1] : -
        #num_params[2] : x2, y1
        #num_params[3] : x2,y1 k2

        elif Model == '3be': #20240514
            Tmin = [-9999,p[0],p[1],9999]
            Tmax = [p[0],p[1],9999,9999]
            num_params = [3,4,3,-9999]
        #x0,   x1,   x2   y0  y1   k0    k1    k2
        #num_params[0] : x0,  y0, k0
        #num_params[1] : x0, x1, y1, k1
        #num_params[2] : x1, y1
        #num_params[3] : -
        
        
        SSE=[]
        CVRMSE=[]
        NBPOINT=[]
        for item in range(len(Tmin)):
            T0 = Tmin[item]
            T1 = Tmax[item]
            Filtre_x = (x>T0) & (x<= T1)
            NBPOINT.append(len(Dyfy[Filtre_x]))
            if len(Dyfy[Filtre_x])==0:
                SSE.append(9e999)
                CVRMSE.append(9e999)
            else:
                try:
                    SSE.append(np.sum(np.sum(np.square(Dyfy[Filtre_x]))))
                except:
                    SSE.append(9e999)
                nparam = num_params[item]
                #try:
                CVRMSE.append(np.sqrt(SSE[item] / (len(Filtre_x)-nparam)) / np.mean(y[Filtre_x]))
                #except:
                #  CVRMSE.append(-1)
                    
        return [SSE, CVRMSE,NBPOINT]

    ###############################################################################


    def calcul(self):
        """
        Method to calculate the PRISM.

        Returns:
            None
        """
        #TO DO : Ameliorer la comparaison 2 seg (ch et cl)

        Methode = 'dogbox' #'dogbox',‘lm’, ‘trf’, (‘dogbox’ : converge mieux selon les version de numpy/scipy mais pas forcemment disponible en Java)

        x = self.x
        y = self.y  

        try:
            pini=self.get_param_ini_prism()
        except:
            pini = [-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 2.0] #self.get_param_ini_prism()
        
        SSE = []
        num_params = [3, 5]#, 7]
        valide = np.ones(5)

        r2_4 = np.zeros(3)
        r2_3 = np.zeros(3)
        r2_2ch = np.zeros(3)
        r2_2cl = np.zeros(3)
        r2_3bi = np.zeros(3) #20240514

                    #    x0, x1, x2,     y0,     y1,      k0,      k1,      k2
        boundMin = [-np.inf,  2, 15,      0,      0, -np.inf, -np.inf,      0]
        boundMax = [      0, 20, 25, np.inf, np.inf,  np.inf,       0, np.inf]
        bounds=(boundMin, boundMax)
        pini = list(np.clip(pini, boundMin, boundMax))
                
        if self.P_4seg: 
            num_params = [3, 5, 7] 

            try: #try piecewise_linear_4seg
                p4 , e4 = optimize.curve_fit(self.piecewise_linear_4seg, x, y, pini, bounds=bounds, method=Methode) #bounds=bounds,
                p4[6] = (p4[3]-p4[4])/(p4[0]-p4[1])
                p4 = np.round(p4,4)
                
                Dyfy = y-self.piecewise_linear_4seg(x,*p4) # residuals # y-self.piecewise_linear_4seg(x,*p4)
                
                [SSE4,CVRMSE4,NBPOINT4] = self.SSE_CVRMSE_seg(Dyfy,x,y,p4,'4sg')
                # Pente en chauffage plus petite que 0
                if(p4[6]>=0):
                    valide[3] = False
                # Pente en clim plus grande que 0
                if(p4[7]<=0):
                    valide[3] = False

                if(p4[5]<0):#on garde le 4 segments pour la bienergie- exclue PAC+elec
                    valide[3] = False
    
                # Il doit y avoir au moins
                if(len(x[(x>p4[1]) & (x<p4[2])])<3):# Au moins 3 points dans le segments de bas : Alain 2016-09-09
                    p4[1] = (p4[6]*p4[1]-p4[7]*p4[2])/(p4[6]-p4[7])
                    p4[2] = p4[1]
    
                # Pente T <<< doit avoir plus que 5 points
                xarg = np.where(x<p4[0])[0].transpose()
                if(len(xarg)>5):
                    x2=np.ones((len(xarg),2))
                    x2[:,0]=x[xarg[:]]
                    y2 = y[xarg]
                    result = sm.OLS( y2, sm.tools.add_constant(x2)).fit()
                    r2_4[0] = result.rsquared

                    if(result.pvalues[0] > 1.0-0.95):
                        valide[3] = False
                else:
                    valide[3] = False
    
                # Pente en chauffage significativement differente de 0
                xarg = np.where((x<p4[1]) & (x>p4[0]))[0].transpose()
                if(len(xarg)>5):
                    x2=np.ones((len(xarg),2))
                    x2[:,0]=x[xarg[:]]
                    y2 = y[xarg]
                    result = sm.OLS( y2, sm.tools.add_constant(x2) ).fit()
                    r2_4[1] = result.rsquared
                    if(result.pvalues[0] > 1.0-0.95):
                        valide[3] = False
                else:
                    valide[3] = False
    
                # Pente en clim significativement differente de 0
                xarg = np.where(x>p4[2])[0].transpose()
                if(len(xarg)>5):
                    x2=np.ones((len(xarg),2))
                    x2[:,0]=x[xarg[:]]
                    y2 = y[xarg]
                    result = sm.OLS( y2, sm.tools.add_constant(x2) ).fit()
                    r2_4[2] = result.rsquared
                    if((result.pvalues[0] > 1.0-0.95)):
                        valide[3] = False
                else:
                    valide[3] = False
    
            except:
                valide[3] = False 
                #print('Fit not found for 4 segments')
        else:
            valide[3] = False

        try: #try piecewise_linear_3be
            p5 , e5 = optimize.curve_fit(self.piecewise_linear_3be, x, y, pini, bounds=bounds, method=Methode) #bounds=bounds,
            p5[6] = (p5[3]-p5[4])/(p5[0]-p5[1])
            p5 = np.round(p5,4)
            
            Dyfy = y-self.piecewise_linear_3be(x,*p5) # residuals # y-self.piecewise_linear_3be(x,*p5)
            
            [SSE5,CVRMSE5,NBPOINT5] = self.SSE_CVRMSE_seg(Dyfy,x,y,p5,'3be')
            # Pente en chauffage plus petite que 0
            if(p5[6]>=0):
                valide[4] = False
            
            if(p5[5]<0):#on garde le 4 segments pour la bienergie- exclue PAC+elec
                valide[4] = False

            # Il doit y avoir au moins
            if(len(x[(x>p5[1]) & (x<p5[2])])<3):# Au moins 3 points dans le segments de bas : Alain 2016-09-09
                p5[1] = (p5[6]*p5[1]-p5[7]*p5[2])/(p5[6]-p5[7])
                p5[2] = p5[1]

            # Pente T <<< doit avoir plus que 5 points
            xarg = np.where(x<p5[0])[0].transpose()
            if(len(xarg)>5):
                x2=np.ones((len(xarg),2))
                x2[:,0]=x[xarg[:]]
                y2 = y[xarg]
                result = sm.OLS( y2, sm.tools.add_constant(x2)).fit()
                r2_3bi[0] = result.rsquared
                
                if(result.pvalues[0] > 1.0-0.95):
                    valide[4] = False
            else:
                valide[4] = False

            # Pente en chauffage significativement differente de 0
            xarg = np.where((x<p5[1]) & (x>p5[0]))[0].transpose()
            if(len(xarg)>5):
                x2=np.ones((len(xarg),2))
                x2[:,0]=x[xarg[:]]
                y2 = y[xarg]
                result = sm.OLS( y2, sm.tools.add_constant(x2) ).fit()
                r2_3bi[1] = result.rsquared
                if(result.pvalues[0] > 1.0-0.95):
                    valide[4] = False
            else:
                valide[4] = False

        except:
            valide[4] = False # Alain : 2016-09-06
            #print('Fit not found for 4 segments')

        try: #try piecewise_linear_3seg
            #Methode = 'lm'     
            p3 , e3 = optimize.curve_fit(self.piecewise_linear_3seg, x, y, pini, bounds=bounds, method=Methode)#bounds=bounds, [-10.0, 10.0, 20.0, 72, 24, -2.0, -2.0, 1.0])#,method=Methode)
            p3 = np.round(p3,4)
            #Methode = 'lm' #'dogbox',‘lm’, ‘trf’, (‘dogbox’ : converge mieux mais pas forcemment disponible en Java)
            
            #p3 , e3 = optimize.curve_fit(self.piecewise_linear_3seg, x, y, p3)#,method='lm')
            Dyfy = y-self.piecewise_linear_3seg(x,*p3)
            [SSE3,CVRMSE3,NBPOINT3] = self.SSE_CVRMSE_seg(Dyfy,x,y,p3,'3sg')


            # Validation de la pente en chauffage
            if(p3[6]>=0):
                valide[2] = False

            xarg = np.where(x<p3[1])[0].transpose()
            if(len(xarg)>5):
                x2=np.ones((len(xarg),2))
                x2[:,0]=x[xarg[:]]
                y2 = y[xarg]
                result = sm.OLS( y2, sm.tools.add_constant(x2) ).fit()
                r2_3[1] = result.rsquared
                if(result.pvalues[0] > 1.0-0.95):
                    valide[2] = False
            else:
                valide[2] = False

            # Validation de pente en climatisation
            if(p3[7]<=0):
                valide[2] = False
            xarg = np.where(x>p3[2])[0].transpose()
            if(len(xarg)>5):
                x2=np.ones((len(xarg),2))
                x2[:,0]=x[xarg[:]]
                y2 = y[xarg]
                result = sm.OLS( y2, sm.tools.add_constant(x2) ).fit()
                r2_3[2] = result.rsquared
                if((result.pvalues[0] > 1.0-0.95)):
                    valide[2] = False
            else:
                valide[2] = False

            # Verifie si il s'agit d'un 2 segments chauffage/cllimatisation
            if(p3[1]>p3[2]):
                p3[1] = (p3[6]*p3[1]-p3[7]*p3[2])/(p3[6]-p3[7])
                p3[2] = p3[1]
            if(len(x[(x>p3[1]) & (x<p3[2])])<3):# Au moins 3 points dans le segments de bas : Alain 2016-09-09
                p3[1] = (p3[6]*p3[1]-p3[7]*p3[2])/(p3[6]-p3[7])
                p3[2] = p3[1]
        except:
            valide[2] = False
            #print('Fit not found for 3 segments')

        try: #try piecewise_linear_2seg_ch 
            p2ch , e2ch = optimize.curve_fit(self.piecewise_linear_2seg_ch, x, y, pini, bounds=bounds, method=Methode)# bounds=bounds,#[-10.0, 10.0, 20.0, 10, 10, -2.0, -2.0, 1.0]
            p2ch=np.round(p2ch,4)
            # Validation des pentes
            Dyfy = y-self.piecewise_linear_2seg_ch(x,*p2ch)
            [SSE2ch,CVRMSE2ch,NBPOINT2ch] = self.SSE_CVRMSE_seg(Dyfy,x,y,p2ch,'2ch')
            
            if(p2ch[6]>=0):
                valide[1] = False
            xarg = np.where(x<p2ch[1])[0].transpose()
            if(len(xarg)>5):
                x2=np.ones((len(xarg),2))
                x2[:,0]=x[xarg[:]]
                y2 = y[xarg]
                result = sm.OLS( y2, sm.tools.add_constant(x2) ).fit()
                r2_2ch[1] = result.rsquared
                if(result.pvalues[0] > 1.0-0.95):
                    valide[1] = False
            else:
                valide[1] = False
        except:
            valide[1] = False
            #print('Fit not found for 2 segments chauffage')

        try:#try piecewise_linear_2seg_cl
            p2cl , e2cl = optimize.curve_fit(self.piecewise_linear_2seg_cl, x, y, pini, bounds=bounds, method=Methode)#bounds=bounds,#[-10.0, 10.0, 20.0, 10, 10, -2.0, -2.0, 1.0]
            p2cl=np.round(p2cl,4)
            Dyfy = y-self.piecewise_linear_2seg_cl(x,*p2cl)
            [SSE2cl,CVRMSE2cl,NBPOINT2cl] = self.SSE_CVRMSE_seg(Dyfy,x,y,p2cl,'2cl')
            # Validation des pentes
            if(p2cl[7]<=0):
                valide[0] = False
            xarg = np.where(x>p2cl[2])[0].transpose()
            if(len(xarg)>5):
                x2=np.ones((len(xarg),2))
                x2[:,0]=x[xarg[:]]
                y2 = y[xarg]
                result = sm.OLS( y2, sm.tools.add_constant(x2) ).fit()
                r2_2cl[2] = result.rsquared
                if((result.pvalues[0] > 1.0-0.95)):
                    valide[0] = False
            else:
                valide[0] = False
        except:
            valide[0] = False
            #print('Fit not found for 2 segments climatisation')


        # Calcul du SSE          
            
        try:
            SSE_ch = np.sum(np.sum(np.square(y-self.piecewise_linear_2seg_ch(x,*p2ch))))
        except:
            SSE_ch=9e999
        try:
            SSE_cl = np.sum(np.sum(np.square(y-self.piecewise_linear_2seg_cl(x,*p2cl))))
        except:
            SSE_cl=9e999
            
            
        if((SSE_ch < SSE_cl) | ((valide[1]==1) & (valide[0]==0))):
            if valide[1]:
                SSE.append(np.sum(np.sum(np.square(y-self.piecewise_linear_2seg_ch(x,*p2ch)))))
            else:
                SSE.append(9e999)
            p = copy.copy(p2ch)
            r2 = copy.copy(r2_2ch)
            p[0], p[2], p[3], p[5], p[7] = np.nan, np.nan, np.nan, np.nan, np.nan
            model = '2ch'
            CVRMSE = np.sqrt(SSE_ch / (len(x)-num_params[0])) / np.mean(y) # Simon
            CVRMSEseg = CVRMSE2ch
            NBPOINTseg=NBPOINT2ch
        else:#par défaut
            if valide[0] :
                SSE.append(np.sum(np.sum(np.square(y-self.piecewise_linear_2seg_cl(x,*p2cl)))))
                p = copy.copy(p2cl)
            else:
                SSE.append(9e999)
                p = copy.copy(p2cl)
                p[7] = 0
                
            #p = copy.copy(p2cl)
            r2 = copy.copy(r2_2cl)
            p[0], p[1], p[3], p[5], p[6] = np.nan, np.nan, np.nan, np.nan, np.nan
            model = '2cl'
            CVRMSE = np.sqrt(SSE_cl / (len(x)-num_params[0])) / np.mean(y)  # Simon
            CVRMSEseg = CVRMSE2cl
            NBPOINTseg=NBPOINT2cl

        try:
            SSE_3seg = np.sum(np.sum(np.square(y-self.piecewise_linear_3seg(x,*p3))))
        except:
            SSE_3seg=9e999
        try:
            SSE_3be = np.sum(np.sum(np.square(y-self.piecewise_linear_3be(x,*p5))))
        except:
            SSE_3be=9e999
			
        if((SSE_3seg < SSE_3be)):
            if valide[2]:
                SSE.append(np.sum(np.sum(np.square(y-self.piecewise_linear_3seg(x,*p3)))))
                model3 = '3sg'
                p3[0], p3[3], p3[5] = np.nan, np.nan, np.nan
            elif valide[4]:
                SSE.append(np.sum(np.sum(np.square(y-self.piecewise_linear_3be(x,*p5)))))
                #SSE.append(9e999)
                p3 = copy.copy(p5)
                r2_3 = copy.copy(r2_3bi)
                
                p3[2], p3[7] = np.nan, np.nan
                model3 = '3be'
                SSE3 = SSE5
                CVRMSE3 =CVRMSE5
                NBPOINT3 = NBPOINT5
            
            else:
                SSE.append(9e999)
            
			
        else:#par défaut
            if valide[4] :
                SSE.append(np.sum(np.sum(np.square(y-self.piecewise_linear_3be(x,*p5)))))
                 #SSE.append(9e999)
                p3 = copy.copy(p5)
                r2_3 = copy.copy(r2_3bi)
                
                p3[2], p3[7] = np.nan, np.nan
                model3 = '3be'
                SSE3 = SSE5
                CVRMSE3 =CVRMSE5
                NBPOINT3 = NBPOINT5
            elif valide[2]:
                SSE.append(np.sum(np.sum(np.square(y-self.piecewise_linear_3seg(x,*p3)))))
                model3 = '3sg'
                p3[0], p3[3], p3[5] = np.nan, np.nan, np.nan
            else:
                SSE.append(9e999)
                
            
        if self.P_4seg:
            if valide[3] :
                SSE.append(np.sum(np.sum(np.square(y-self.piecewise_linear_4seg(x,*p4)))))
            else:
                SSE.append(9e999)

		
        # Choix du modele
        F=self.Test_Fisher(SSE, num_params, len(x), 0.05)
        

        if(F[0,0]):
            p = copy.copy(p3)
            r2 = copy.copy(r2_3)
			
            model = model3
            CVRMSE = np.sqrt(SSE[1] / (len(x)-num_params[1])) / np.mean(y)  # Simon
            #p[0], p[3], p[5] = np.nan, np.nan, np.nan
            CVRMSEseg = CVRMSE3
            NBPOINTseg=NBPOINT3

        if self.P_4seg:
            if(F[0,1]): #changement brice [0,1], car [1,0] jamais traité dans test fisher (model 3 vs 4)
                    p = copy.copy(p4)
                    r2 = copy.copy(r2_4)
                    model = '4sg'
                    CVRMSE = np.sqrt(SSE[2] / (len(x)-num_params[2])) / np.mean(y)  # Simon
                    CVRMSEseg = CVRMSE4
                    NBPOINTseg=NBPOINT4
            else:
                if(F[1,1]):
                    p = copy.copy(p4)
                    r2 = copy.copy(r2_4)
                    model = '4sg'
                    CVRMSE = np.sqrt(SSE[2] / (len(x)-num_params[2])) / np.mean(y)  # Simon
                    CVRMSEseg = CVRMSE4
                    NBPOINTseg=NBPOINT4

        p=np.round(p,4) #
        self.param = {"Modèle":model,
                      "modele_ini": self.Model_ini,
                     "Tsat [°C]": p[0],
                     "Tch [°C]": p[1],
                     "Tcl [°C]": p[2],
                     "ksat [W/°C]": p[5],
                     "kch [W/°C]": p[6],
                     "kcl [W/°C]": p[7],
                     "Base [kW]": p[4],
                     "r2 sat": r2[0],
                     "r2 ch": r2[1],
                     "r2 cl": r2[2],
                     "CVRMSE": CVRMSE,
                     "CVRMSE_segCH0": CVRMSEseg[0],
                     "CVRMSE_segCH": CVRMSEseg[1],
                     "CVRMSE_segB": CVRMSEseg[2],
                     "CVRMSE_segCL": CVRMSEseg[3],
                     "NBPOINTsegCH0": NBPOINTseg[0],
                     "NBPOINTsegCH": NBPOINTseg[1],
                     "NBPOINTsegB": NBPOINTseg[2],
                     "NBPOINTsegCL": NBPOINTseg[3],
                     "NbPointMoins10": int(np.sum(self.x < -10)),
                     "NbPointplus15": int(np.sum(self.x > 15)),
                     "NbPointTot": int(self.x.size)}
            
        self.model = model
        self.p = p
        return self.param
    
if __name__ == "__main__":
    
    #Données arbitraires aléatoires
    data = {'4seg' : {'Temperature': np.linspace(-30, 30, 100),
                 'Conso': Prism.piecewise_linear_4seg(None, np.linspace(-30, 30, 100), *[-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 1.0])+ np.random.rand(100)*5},
            '3seg' : {'Temperature': np.linspace(-30, 30, 100),
                 'Conso': Prism.piecewise_linear_3seg(None, np.linspace(-30, 30, 100), *[-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 1.0])+ np.random.rand(100)*5},
            '3be' : {'Temperature': np.linspace(-30, 30, 100),
                 'Conso': Prism.piecewise_linear_3be(None, np.linspace(-30, 30, 100), *[-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 1.0])+ np.random.rand(100)*5},
            '2ch' : {'Temperature': np.linspace(-30, 30, 100),
                 'Conso': Prism.piecewise_linear_2seg_ch(None, np.linspace(-30, 30, 100), *[-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 1.0])+ np.random.rand(100)*5},
            '2cl' : {'Temperature': np.linspace(-30, 30, 100),
                 'Conso': Prism.piecewise_linear_2seg_cl(None, np.linspace(-30, 30, 100), *[-10.0, 10.0, 20.0, 72, 24, 2.4, -2.4, 1.0])+ np.random.rand(100)*5},
            }

    mod = '4seg'
    list_P = data[mod]['Conso']
    list_T = data[mod]['Temperature'] 

    ob_Prism = Prism(QuotikWh = list_P, QuotiTemp = list_T)
    res = ob_Prism.calcul()
    print(ob_Prism.param) #dict résultats
    
    ob_Prism.trace() #trace le graphique