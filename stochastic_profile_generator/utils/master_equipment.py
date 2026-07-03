from random import random
from stochastic_profile_generator.utils.data import Data, Grp_data
import numpy as np
from datetime import timedelta 
import os
import pandas as pd
from utils import get_project_configuration
from pathlib import Path

class MasterEquipment(object):

    FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_DIR = os.path.abspath(FILE_DIR + "/../")  # répertoire supérieur
    
    def __init__(self,M,params):
        self.params = params
        self.M = M

        if 'Projection' in self.params:
            self.Projection = self.params['Projection']
        else:
            self.Projection = {'Activer': False}
        
        self.Type = self.params['Type']  # obligatoire
        
        self.configuration_ind() # configu individuelle des equip.

    def configuration_ind(self):
        pass
        
    def Calcul_Equipement(self,occ_profile, act_profile, time_simu):  # programmer chaque equipements indépendament

        self.occ_profile = occ_profile  # 10 min
        self.act_profile = act_profile  # 1 min
        self.time_simu = time_simu  # x min, simulation parc //pour crest

        self.Init()
        self.Init_ind() # initialisation personifiée
        self.Get_data()
        self.Calcul_all_Time()

        #if (self.model == 'lte'):#modele presence et activité
        if len(self.Puissance_temp.time) != len(self.time_simu):
            self.Puissance.data = self.Puissance_temp.interpol(self.time_simu)
        else:
            self.Puissance.data = self.Puissance_temp.data
        
        if (sum(self.EauChaude_temp.data) !=0):
            if len(self.EauChaude_temp.time) != len(self.time_simu):
                self.EauChaude.data = self.EauChaude_temp.interpol(self.time_simu)
            else:
                self.EauChaude.data = self.EauChaude_temp.data
                     
        self.Gain_interne()
        
    def Init_ind(self):
        pass
    
    def Init(self):
        if self.model == 'lte':#modele presence et activité
            self.Puissance_temp = Data(self.Type, '-', 0, self.time_simu, [0]*len(self.time_simu))
            self.EauChaude_temp = Data(self.Type, '-', 0, self.time_simu, [0]*len(self.time_simu))
            
        else: # cret
            self.Puissance_temp = Data(self.Type, '-', 0, self.act_profile.Grp_data['Act_TV'].time, [0]*len(self.act_profile.Grp_data['Act_TV'].time))
            self.EauChaude_temp = Data(self.Type, '-', 0, self.act_profile.Grp_data['Act_TV'].time, [0]*len(self.act_profile.Grp_data['Act_TV'].time))

        self.Puissance = Data(self.Type, '-', 0, self.time_simu, [0]*len(self.time_simu))
        self.Gain = Data(self.Type, '-', 0, self.time_simu, [0]*len(self.time_simu))
        self.EauChaude = Data(self.Type, '-', 0, self.time_simu, [0]*len(self.time_simu))

        if self.Tarif_HQ == 'TDT':
            self.get_TDT_periode() # période de haut tarif issue du fichier
            self.TDT_Time_tarif() # créer une timeserie avec haut/bas tarif (TRUE / FALSE)
 
    def Get_data(self):
        pass
    
    def Get_data_evolution(self, Annee=2017):
        params = {'Type':self.Type}
        cls_data = appliances.Equ_Evol(params)
        self.Data_Evol = cls_data.get_data(Annee = Annee)
        
    def Gain_interne(self):

        self.Gain.data = list(np.multiply(self.Puissance.data,self.QGain))

    # CREST model
    def GetMonteCarloNormalDistGuess(self,dMean, dSD):
        from random import random
        from math import exp
        # Guess a value from a normal distribution for a given mean and standard deviation

        if dMean == 0:
            return 0
        while 1:
            # Guess a value
            iGuess = (random() * (dSD * 8)) - (dSD * 4) + dMean
            # See if this is likely
            px = (1 / (dSD * ((2 * 3.14159) ** 0.5))) * exp(-((iGuess - dMean) ** 2) / (2 * dSD * dSD))
            # End the loop if this value is okay
            if (px >= random()):
                return iGuess

    def Calcul_all_Time(self):
        pass
    
    def Usage_action(self,time):
       # determination de l’action (Activer, Deplacer, Annuler)
       # selon l’heure de la simulation, un fichier des heures de tarif, le type de tarif, le type d’equipement, les attributs du menage
       #Probability_active = 0.35 # devrait provenir d'un fichier txt
       #Probability_deplace = 0.6
       

       
       if self.Tarif_HQ == 'TDT':
           self.Methode_GDP(time)
           # 1 verifier l'action faite par le menage
           if self.GDPPeriode:
               rand_nb = random()
               if (rand_nb < self.TDT_Probability_active ):
                   self.Action = 'Activer'
               elif (rand_nb < self.TDT_Probability_active + self.TDT_Probability_deplace):
                   self.Action = 'Deplacer'
               else:
                   self.Action = 'Annuler'
           else:
               self.Action = 'Activer'
                       
       else:
           if self.Action != 'Activer':
               self.Action = 'Activer'
    
    def Methode_GDP(self,time): #utilitser un dictionnaire plutot qu'un dataframe
        # a partir des donnees chargees en debut de methode Calcul_all_Time (self.Eq_TDT)
        # regarde si on est en periode de haut tarif
        if self.Tarif_HQ == 'TDT':
            if  self.TDT_Time.loc[time,'Haut_Tarif']: #TRUE = haut tarif
                self.GDPPeriode = True
            else:
                self.GDPPeriode = False
        else:
            if self.GDPPeriode != False:
                self.GDPPeriode = False
#            else:  # bas tarif
#                rand_nb = random()
#                Probability_antipation = #loi a definir
#                if (rand_nb < Probability_antipation ):
#                    self.GDPPeriode = True
#                else:
#                    self.GDPPeriode = False


    def get_TDT_periode(self): # charge le fichier de periode Haut tarif
                
        TDT_periode_name = "TDT_periode.csv"
        TDT_periode_path=os.path.join(self.PROJECT_DIR,'Donnees','Tarification', TDT_periode_name)
        
        self.TDT_periode = pd.read_csv(TDT_periode_path,
                                            sep = ';',
                                            parse_dates = ['Debut','Fin'])

        TDT_action_name = "TDT_action.csv"
        TDT_action_path=os.path.join(self.PROJECT_DIR,'Donnees','Tarification', TDT_action_name)
        
        self.TDT_action = pd.read_csv(TDT_action_path,
                                            sep = ';',
                                            index_col = 0)

        self.TDT_Probability_active = self.TDT_action.loc[self.Type,'Activation']
        self.TDT_Probability_deplace = self.TDT_action.loc[self.Type,'Deplacement']
        
    def TDT_Time_tarif(self):  # créer une timeserie avec haut/bas tarif (TRUE / FALSE)
        
        self.TDT_Time=pd.DataFrame(index = self.Puissance_temp.time, columns =['Haut_Tarif']) # ne pas utiliser de dataframe car trop long pour aller chercher les données avec .loc - transformer le dataframe en dictionnaire à la fin de cette méthode pour accélérer la recherche
        self.TDT_Time.loc[:,'Haut_Tarif'] = False
        
        for event in self.TDT_periode.index:
            dt_debut = random() * timedelta(hours = 1) # devrait dépendre de l'équipement
            dt_fin = random() * timedelta(hours = 1)
            filtre = (self.TDT_Time.index>=self.TDT_periode.loc[event,'Debut']-dt_debut) & (self.TDT_Time.index<=self.TDT_periode.loc[event,'Fin']+dt_fin)
            self.TDT_Time.loc[filtre,'Haut_Tarif'] = True