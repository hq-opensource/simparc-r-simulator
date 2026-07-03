# -*- coding: utf-8 -*-
"""
Created on Tue Jan 28 09:14:56 2020

Modèle du SPA résidentiel
Concept basé sur le modèle de JAG et les Données de ASE (puissance nominale et cyclage du chauffage)
Calibré sur :
- Sondage : Ad hoc recherche : Utilisation de l'élec. dans le marché résidentiel (2014)
- Présentation : Projet GDPR, lot 1, Spa - résumé, Sondage Utilisation des spas (4 juillet 2014)

@author: Francois Laurencelle
"""
# Libraries
import numpy as np
from datetime import timedelta, datetime
from random import random
import pandas as pd

# Local libraries
from stochastic_profile_generator.utils.data import Data
from stochastic_profile_generator.utils.master_equipment import MasterEquipment

class Tmaison:
    """Minimal container for TSPA simulation"""
    def __init__(self):
        pass

class TSPA(MasterEquipment):
    """
     Classe qui gère le spa :
     .. todo:: 
         1. SPA intérieur
         2. Adapter à l'horaire d'occupation
    """
    #FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    #PROJECT_DIR = os.path.abspath(FILE_DIR + "/../")  # répertoire supérieur
    
    def Get_data(self):

        #Puissance pompe Pmass (W), Pertes additionnelles m (W/m2) et b (W/m2/°C)
        self.Pmass = 1800 #W pompe
        self.Pchg = 6000 #W chauffage
        self.m = [  21.1, 14.5][self.prot_vent]
        self.b = [ 623.3,377.1][self.prot_vent]  

        #UA (W/°C), Aeff (m2), Fvent (1 ou +),
        self.UA    = {3: 7.29, 4: 8.43, 5: 9.66, 6: 10.10, 7: 11.03 }[self.nb_places]
        self.Aeff  = {3: 1.64, 4: 1.88, 5: 2.42, 6:  2.82, 7:  3.11 }[self.nb_places]
        
        if self.Projection['Activer'] == True:
            self.Get_data_evolution(Annee=self.Projection['Annee'])
            
            self.UA = self.UA * self.Data_Evol['Efficacite']
            self.Aeff = self.Aeff * self.Data_Evol['Efficacite']
            self.Pmass = self.Pmass * self.Data_Evol['Efficacite']
            
    def configuration_ind(self):

        #non HPXML parameters (SPA-specific parameters)
        #'Spa_Presence': ['Oui', 'Non']
        #'Spa_Logement': ['Aucun', 'Exterieur', 'Interieur']
        #'Spa_Saison': ['Aucun', 'Pas utilisé', 'Ne sait pas', 
        #               'Toute_Saison', 'Printemps', 'Ete', 'Automne', 'Hiver',
        #               'Printemps_Ete', 'Printemps_Automne', 'Printemps_Hiver', 'Ete_Automne', 'Ete_Hiver', 'Automne_Hiver',
        #               'Printemps_Ete_Automne', 'Printemps_Automne_Hiver', 'Ete_Automne_Hiver']
        #'Spa_Utilisation_SaisonChaude' : ['Aucun', 'Ne sais pas', 'Constant', 'Augmentation']
        #'Spa_Utilisation_SaisonFroide' : ['Aucun', 'Ne sais pas', 'Constant', 'Augmentation']
        #'Spa ChaufType' : ['none', 'electric resistance', 'gas fired', 'heat pump']

        #Dimension du SPA en nombre de places
        #Le SPA le plus populaire comporte 6 places

        self.Tzone_Spa_int = 20 #Température intérieure [zone] stable pour les SPA intérieurs

        if 'nb_places' in self.params:
            self.nb_places=self.params['nb_places']
        else:
            poss =          [ 3, 3,  4,  5,  6,  7,  7] #Possibilités
            occu = np.array([ 2, 6, 28, 35,165, 34, 32]) #Occurrences
            self.nb_places = np.random.choice(poss, p=occu/sum(occu))

        #Dans un abri protegé contre le vent 
        #Protection totale (27%) = True
        #Protection partielle (73%) = False)            
        if 'prot_vent' in self.params:
            self.prot_vent = self.params['prot_vent']
        else:
            self.prot_vent = np.random.random() < 0.27
        if ('Spa_Logement' in self.params) and (self.params['Spa_Logement'] == 'Interieur'):
            self.prot_vent = True

        #Saison d'utilisation et de maintien chauffé du SPA
        #Toute l'année (54%) = ANNEE
        #Seulement l'été (46%)
        
        #if 'saison' in self.params:
        #    self.saison = self.params['saison']
        #else:
        #    self.saison = ['ANNEE','ETE'][random()<0.54]
        if "Spa_Saison" in self.params:
            saison_param = self.params["Spa_Saison"]
            if saison_param in ['Toute_Saison', 'Hiver', 'Printemps_Hiver', "Ete_Hiver", "Automne_Hiver",
                                'Printemps_Automne_Hiver', 'Ete_Automne_Hiver']:
                self.saison = 'ANNEE'
            elif saison_param in ['Printemps', 'Ete', 'Automne',
                                 'Printemps_Ete', 'Printemps_Automne', 'Ete_Automne',
                                 'Printemps_Ete_Automne',]:
                self.saison = 'ETE'
            else:#'Aucun', 'Pas utilisé', 'Ne sait pas'
                self.saison = ['ANNEE','ETE'][random()<0.54]
        else:
            self.saison = ['ANNEE','ETE'][random()<0.54]
        #Fréquence d'utilisation du SPA en été (FAIBLE,MOYEN,ELEVE)
        #ELEVE (3 fois ou plus par semaine ou 0.57/jour)
        #MOYEN (1 ou 2 fois par semaine ou 0.21/jour)
        #FAIBLE (moins de une fois par semaine ou 0.11/jour)
        if 'freq_util_ete' in self.params:
            self.freq_util = self.params['freq_util']
        else:
            poss =          ['FAIBLE','MOYEN','ELEVE'] #Possibilités
            occu = np.array([      18,     20,     62]) #Occurrences
            self.freq_util_ete = np.random.choice(poss, p=occu/sum(occu))
        
        #Fréquence d'utilisation du SPA en hiver (FAIBLE,MOYEN,ELEVE)
        if 'freq_util_hiv' in self.params:
            self.freq_util = self.params['freq_util']
        else:
            poss =          ['FAIBLE','MOYEN','ELEVE'] #Possibilités
            occu = np.array([      35,     28,     37]) #Occurrences
            self.freq_util_hiv = np.random.choice(poss, p=occu/sum(occu))
        
        #Température de consigne hors utilisation en été
        if 't_non_util_ete' in self.params:
            self.t_non_util_ete = self.params['t_non_util_ete']
        else:
            self.t_non_util_ete = 33.5

        #Température de consigne hors utilisation en hiver
        if 't_non_util_hiv' in self.params:
            self.t_non_util_hiv = self.params['t_non_util_hiv']
        else:
            self.t_non_util_hiv = 36.3
        
        #Température de consigne en utilisation en été
        if 't_util_ete' in self.params:
            self.t_util_ete = self.params['t_util_ete']
        else:
            self.t_util_ete = 34.2

        #Température de consigne en utilisation en hiver
        if 't_util_hiv' in self.params:
            self.t_util_hiv = self.params['t_util_hiv']
        else:
            self.t_util_hiv = 37.4
        
        #Durée d'un bain en été (en heure)
        if 'duree_bain_ete' in self.params:
            self.duree_bain_ete = self.params['duree_bain_ete']
        else:
            self.duree_bain_ete = 56/60 #heures        

        #Durée d'un bain en hiver (en heure)
        if 'duree_bain_hiv' in self.params:
            self.duree_bain_hiv = self.params['duree_bain_hiv']
        else:
            self.duree_bain_hiv = 40/60 #heures
        
        #Horaire quotidien d'utilisation en été (idem semaine et fin de semaine)
        #np.array(24 valeurs de probabilité de l'heure du bain, inutile de pondérer)
        if 'hor_util_ete' in self.params:
            self.hor_util_ete = self.params['hor_util_ete']
        else:
            self.hor_util_ete = np.array([0,0,0,0,0,0,0,0,1,2,2,2,2,1,1,2,3,4,4,4,2,1,0,0])

        #Horaire quotidien d'utilisation en hiver (idem semaine et fin de semaine)
        #np.array(24 valeurs de probabilité de l'heure du bain, inutile de pondérer)
        if 'hor_util_hiv' in self.params:
            self.hor_util_hiv = self.params['hor_util_hiv']
        else:
            self.hor_util_hiv = np.array([0,0,0,0,0,0,0,0,1,2,2,2,2,1,1,2,3,4,4,4,2,1,0,0])
            
        #DAte de début de l'été au 15 avril avec écart type de +/- 10jours (référée à 2000)
        self.debut_ete = pd.Timestamp(datetime(2000, 4, 15) + timedelta(days = int(max(min(np.random.standard_normal(),2),-2)*10)))
        
        #Date debut de l'hiver au 1e novembre avec écart type de +/- 10jours (référée à 2000)
        self.debut_hiv = pd.Timestamp(datetime(2000, 11, 1) + timedelta(days = int(max(min(np.random.standard_normal(),2),-2)*10)))


        if self.prot_vent:
            self.Fvent = 1
        else:
            self.Fvent = {3: 1.79, 4: 1.68, 5: 1.59, 6:  1.57, 7:  1.52 }[self.nb_places] 
          
            
        
    def Calcul_all_Time(self): 
        Echg_max = np.random.uniform(800, 1200)
        Echg = np.random.random()*Echg_max #0
        Pchg = 0
        dt = self.M.dt
        text_lisse = self.M.Donnees_Meteo['DryBulb'].data[0]
        w_lisse = 1/24 * dt
        doy_old = -1
        doy_debut_ete = self.debut_ete.dayofyear
        doy_debut_hiv = self.debut_hiv.dayofyear
        
        for k, ts in enumerate(self.time_simu):
            if ('Spa_Logement' in self.params) and (self.params['Spa_Logement'] == 'Interieur'):
                text_lisse = self.Tzone_Spa_int #Température intérieure stable
            else:
                text_lisse = text_lisse * (1 - w_lisse) + w_lisse * self.M.Donnees_Meteo['DryBulb'].data[k]
            heure = ts.hour + ts.minute/60
            doy = ts.dayofyear
            if doy != doy_old:
               eh = ['hiv','ete'][doy > doy_debut_ete and doy<doy_debut_hiv]
               if eh == 'hiv':
                   if self.saison == 'ANNEE':
                       bain_today = random() < {'ELEVE':0.57,'MOYEN':0.21,'FAIBLE':0.11}[self.freq_util_hiv]
                   else:
                       bain_today = False
                   if bain_today:
                       duree_bain = self.duree_bain_hiv #en heures
                       poss = range(24)
                       occu = self.hor_util_hiv
                       heure_bain = np.random.choice(poss, p=occu/sum(occu)) + random()
               else: #if eh == 'ete'
                   bain_today = random()<{'ELEVE':0.57,'MOYEN':0.21,'FAIBLE':0.11}[self.freq_util_ete]
                   if bain_today:
                       duree_bain = self.duree_bain_ete #en heures
                       poss = range(24)
                       occu = self.hor_util_ete
                       heure_bain = np.random.choice(poss, p=occu/sum(occu)) + random()
            doy_old = doy
            
            Pbain = 0
            if eh == 'hiv':
                if self.saison == 'ANNEE':
                    Echg += self.UA * self.Fvent * max(self.t_non_util_ete - text_lisse,0) * dt        
                if bain_today:
                    if heure > heure_bain and heure <= heure_bain + duree_bain:
                        Pbain = self.Pmass
                        Echg += (self.b + self.m * max(self.t_util_hiv - text_lisse ,0)) * self.Aeff * dt
            else: #if eh == 'ete'
                Echg += self.UA * self.Fvent * max(self.t_non_util_ete - text_lisse, 0) * dt
                if bain_today:
                    if heure > heure_bain and heure <= heure_bain + duree_bain:
                        Pbain = self.Pmass
                        Echg += (self.b + self.m * max(self.t_util_ete - text_lisse ,0)) * self.Aeff * dt

            if Pchg == 0 and Echg > Echg_max:
                Pchg = self.Pchg
            if Pchg > 0 and Echg < 0:
                Pchg = 0
            Echg -= Pchg*dt    
            self.Puissance.data[k] = Pchg + Pbain
            
    
    def Init(self):
        self.Puissance = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))
        self.Gain =      Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))
        self.EauChaude = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))

    
    def Calcul_Equipement(self, time_simu):  
        self.time_simu = time_simu  
        self.Init()
        self.Init_ind() # initialisation personifiée
        self.configuration_ind()
        self.Get_data()
        self.Calcul_all_Time()