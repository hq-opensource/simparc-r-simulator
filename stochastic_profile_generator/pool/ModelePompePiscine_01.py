# -*- coding: utf-8 -*-
"""
Created on Mon May 28 09:44:50 2018

Modèle Puissance * Temps       
    obPoolPump = TPompePiscine(Param)
    obPoolPump.Calcul_Equipement(time_simu)
         
Input : 
Param = {'Type': 'POOLPUMP', # obligatoire
         'TypePiscine':  ==>  'HT' pour horts-terre, ou 'CR' pour creusée
         'ModeOperPiscine' : 'AvecMinuterie' (si minuterie), ou 'SansMinuterie' (sans minuterie)
Ouput :
        self.Puissance ==> liste de la puissance de la pompe de piscine en kW à chaque pas en temps de la simulation
        self.Gain ==> liste de gain interne à chaque pas en temps de la simulation (égale 0)
        self.EauChaude ==> liste de consommation d'eau chaude à chaque pas en temps de la simulation (égale 0)
       
Hypothèses :        
- Puissance électrique de la pompe (hors-terre = 735 watt, creusé = 1310 watt) -> en accord avec hypothèses de N. Bigras "Piscine (et SPA) AjoutAjust.20180713 à v020160209.docx"
- Période d'opération : du 1 mai au 10 octobre, avec un variation de +/10 jours
Durée quotidienne avec minuterie : 
    - hors-terre = 10 heures (mai/sept/oct), 6 heures (juin, juil, aout) -> en accord avec hypothèses de N. Bigras "Piscine (et SPA) AjoutAjust.20180713 à v020160209.docx"
    - creusé = 12 heures (mai/sept/oct), 10 heures (juin, juil, aout)) -> en accord avec hypothèses de N. Bigras "Piscine (et SPA) AjoutAjust.20180713 à v020160209.docx"
Démmarage de la pompe aléatoire dans la journée uniformément distribué
 
@author: Simon Sansregret
"""

import numpy as np
from stochastic_profile_generator.utils.data import Data
from datetime import timedelta, datetime
from random import random
from stochastic_profile_generator.utils.master_equipment import MasterEquipment
#import os

class TPompePiscine(MasterEquipment):
    # FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    # PROJECT_DIR = os.path.abspath(FILE_DIR + "/../")  # répertoire supérieur
    
    def configuration_ind(self):
        '''  
        param:
        'PISC_TYPE': self.Peuplement_Maison['PISC_TYPE'],
        'PISC_CHAUFTYPE': self.Peuplement_Maison['PISC_CHAUFTYPE'],
        'PISC_CHAUFSIZE': self.Peuplement_Maison['PISC_CHAUFSIZE'],
        'PISC_MINUTERIE': self.Peuplement_Maison['PISC_MINUTERIE'],
        'PISC_TOILE': self.Peuplement_Maison['PISC_TOILE'],
        'PISC_EXPOSITION': self.Peuplement_Maison['PISC_EXPOSITION'],
        'PISC_CONSIGNE': self.Peuplement_Maison['PISC_CONSIGNE'],
        'PISC_SURFACE': self.Peuplement_Maison['PISC_SURFACE'],
        'PISC_CHAUFFEE': self.Peuplement_Maison['PISC_CHAUFFEE'],
        'PISC_PRESENCE': self.Peuplement_Maison['PISC_PRESENCE']
        '''
        #=====================================================================
        #equivalence réseau bayesien et code de l'équipement
        #---------------------------------------------------------------------
        #Type de piscine
        PISC_TYPE_Dict = {0: 'HT',#'Pas de piscine ext/creusée ou pas de réponse',
                          1: 'CR',#'Extérieure – Creusée',
                          2: 'HT'}#'Extérieure – Hors terre'
        if 'PISC_TYPE' in self.params :
                self.stTypePiscine = PISC_TYPE_Dict[self.params['PISC_TYPE']]
        else:
            self.stTypePiscine = 'HT'
        #---------------------------------------------------------------------
        # Minuterie
        PISC_MINUTERIE_Dict = {0: 'AvecMinuterie',#'Non applicable',
                               1: 'AvecMinuterie',#'Avec minuterie',
                               2: 'SansMinuterie'}#'Sans minuterie',
                      
        if 'PISC_MINUTERIE' in self.params :
            self.stModeOperPiscine = PISC_MINUTERIE_Dict[self.params['PISC_MINUTERIE']]
        else :
           self.stModeOperPiscine =  'AvecMinuterie'
        #---------------------------------------------------------------------

        #Début au 1 mai avec incertitude de +/ 10 jours
        inDayOffet = 5 * np.random.standard_normal() #écart_type de 3 => 95.44% @ +/-2 sig (donc 95% entre -10 et + 10)
        if inDayOffet > 10:
            inDayOffet = 10
        elif inDayOffet<-10:
            inDayOffet = -10
            
            
        self.dtStartSeason = datetime(2000, 5, 1) + timedelta(days = inDayOffet)

        #Fin au 10 octobre avec incertitude de +/ 10 jours
        inDayOffet = int(5 * np.random.standard_normal()) #écart_type de 3 => 95.44% @ +/-2 sig (donc 95% entre -10 et + 10)
        if inDayOffet > 10:
            inDayOffet = 10
        elif inDayOffet<-10:
            inDayOffet = -10
            
        self.dtEndSeason  = datetime(2000, 10, 10) + timedelta(days = inDayOffet )
        
        self.MINPERDAY = 24 * 60
        self.MINPERHOUR = 60
        
        #Nombre de minute écoulé après minuit où la la pompe part
        self.StartTimer  = int(random() * self.MINPERDAY)
        
    def Get_data(self):
        #Puissance électrique de la pompe (hors-terre = 735 watt, creusé = 1310 watt)
        # Nombre d'heure d'opération par jour avec minuterie (hors-terre = 10 heures (mai/sept/oct), 6 heures (juin, juil, aout), creusé = 12 heures (mai/sept), 10 heures (juin, juil, aout))
        if self.stTypePiscine == 'HT' :
            self.PumpPower = 735  #W
            self.diLenghtTimer = {4:12,5:12,6:14,7:14,8:14,9:12,10:12 } #12 heures (mai/sept/oct), 14 heures (juin, juil, aout)
        else:
            self.PumpPower = 1310 #W
            self.diLenghtTimer = {4:14,5:14,6:18,7:18,8:18,9:14,10:14 } #14 heures (mai/sept), 18 heures (juin, juil, aout)

        if self.Projection['Activer'] == True:
            self.Get_data_evolution(Annee=self.Projection['Annee'])        
            self.PumpPower = self.PumpPower * self.Data_Evol['Efficacite']
            
    def Calcul_all_Time(self):
        
        for k in range(len(self.Puissance.time)): 
            ts = self.Puissance.time[k]  
            dtStart = datetime(ts.year, self.dtStartSeason.month, self.dtStartSeason.day) 
            dtEnd = datetime(ts.year, self.dtEndSeason.month, self.dtEndSeason.day) 
            if (ts > dtStart and ts < dtEnd) :
                if self.stModeOperPiscine == 'AvecMinuterie':
                    #self.Puissance.data[k] = 0 deja initialisé a 0
                    intMinuteElapsed = ts.hour*self.MINPERHOUR + ts.minute
                    intLengthTimer = self.diLenghtTimer[ts.month] * self.MINPERHOUR
                    start1 = self.StartTimer
                    start2 = self.StartTimer - self.MINPERDAY
                    bo1 = (intMinuteElapsed > start1) and (intMinuteElapsed < start1 + intLengthTimer)
                    bo2 = (intMinuteElapsed > start2) and (intMinuteElapsed < start2 + intLengthTimer)
                    if bo1 or bo2 :
                        if self.PumpPower!=0:
                            self.Puissance.data[k] = self.PumpPower
                    else :
                        pass # deja initialisé a 0
                        #self.Puissance.data[k] = 0  
                else :
                    if self.PumpPower!=0:
                        self.Puissance.data[k] = self.PumpPower

    def Init(self):
        self.Puissance = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))
        self.Gain = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))
        self.EauChaude = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))


    def Calcul_Equipement(self, time_simu):  # programmer chaque equipements indépendament
        self.time_simu = time_simu  # x min, simulation parc
        self.Init()
        self.Init_ind() # initialisation personifiée
        self.Get_data()
        self.Calcul_all_Time()

# if __name__ == '__main__':
#     import matplotlib.pyplot as plt
#     import sys
#     import pandas as pd
#     path = __file__[:__file__.rfind('ParcVirtuel')-1]
#     sys.path.append(path)
#     time_simu = pd.date_range(start='2017-05-01', end='2017-11-01', freq = '5T').tolist()
#     time_simu = [pd.Timestamp(ele) for ele in time_simu]
    
#     plt.close('all')
#     diCas = {'HT_AvecMin_1' : {'TypePiscine' : 'HT', 'Mode' :  'AvecMinuterie' },
#           'HT_AvecMin_2' : {'TypePiscine' : 'HT', 'Mode' :  'AvecMinuterie' },
#           'HT_sansMin' : {'TypePiscine' : 'HT', 'Mode' :  'SansMinuterie' },
#           'CR_AvecMin_1' : {'TypePiscine' : 'CR', 'Mode' :  'AvecMinuterie' },
#           'CR_AvecMin_2' : {'TypePiscine' : 'CR', 'Mode' :  'AvecMinuterie' }}
          
#     stTypePiscine = 'HT'
#     stModeOperPiscine = 'AvecMinuterie'

#     for Cas in diCas:
#         Param = {'Type': 'POOLPUMP', 'TypePiscine': diCas[Cas]['TypePiscine'], 'ModeOperPiscine' : diCas[Cas]['Mode']} 
#         obPoolPump = TPompePiscine(0,Param) #Pas besoin de passer en argument l'objet Maison  -->  #Obj = Eq_DictClassName[Type_eq](self, self.ListPeuplement['Parametres'][indx])
#         obPoolPump.Calcul_Equipement(time_simu) # Pas besoin de passer en argument les profils d'occupation et d'activités, occ_profile, act_profile, --> #self.Equis[idEqui].Calcul_Equipement(occ_profile, act_profile, self.Donnees_Meteo['DryBulb'].time)
        
#         x = obPoolPump.Puissance.time
#         y = obPoolPump.Puissance.data
#         plt.plot(x,y, label = Cas + ' (kW)')
#     plt.legend(loc = 1 )
#     plt.show()

