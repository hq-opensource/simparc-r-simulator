# -*- coding: utf-8 -*-
"""
Created on Mon May 28 09:44:50 2018

Modèle : Énergie quotidienne = ((a * Text_quot - Tconsigne) - b * (heure ensoleillement quotidien) ]* SurfacePiscine 
où a et b dépendent de l'exposition au soleil et de la présence d'une toile et du type de piscine (CR ou HT) 
Pour la description complète du modèl, voir "ModèlePiscine.xlsx" onglet "Modèle DRMC"
-A prèmière vue, les estimé de ce modèle provenant du modèle duDRMC établit par É.Dumont surestimate la consommation par rapport
 à l'analyse de N.Bigras ;a partir des simulation sur le logiciel Enerpool voir "Comparaison Résultats piscine.xlsx"
- Seulement chauffe-eau à thermopmpe utilisé sur toute la saison est considéré. Utilisation à la demande d'un chauffe-piscine électrique ou à thermopompe n'est pas considéré par le modèle
 
    obPoolHeater = TChauffePiscine(M, Param) 
    obPoolHeater.Calcul_Equipement(time_simu) 

Input :
Param = {'Type' : 'POOLHEATER' # obligatoire
         'Tconsigne':  ==> température de consigne de la piscine en °C
         'TypePiscine': ==>  'HT' pour horts-terre, ou 'CR' pour creusée
         'Toile' :  ==> 'True' (Toile utilsé le plus souvent), ou 'False'  
         'Exposition' :  ==> 'True' (Exposition de la piscine au soleil entièrement exposé), ou 'False'
         'Capacité' :  ==> Capacité de la thermopompe, soit '35kBTU', '55kBTU', '75kBTU', '100kBTU', '125kBTU', '150kBTU', '175kBTU', '200kBTU', '225kBTU', en absence, une capacité fonction de la grandeur de la piscine est choisie
         'PoolDiameter' : ==> Diamètre de la piscine creusé en pied 
         'PoolLength' : ==> Longeur de la piscine creusée en pied
         'PoolWidth' : Largeur de la piscine creusée en pied
Ouput :
        self.Puissance ==> liste de la puissance du chauffe-piscine en kW à chaque pas en temps de la simulation
        self.Gain ==> liste de gain interne à chaque pas en temps de la simulation (égale 0)
        self.EauChaude ==> liste de consommation d'eau chaude à chaque pas en temps de la simulation (égale 0)
        self.PuissanceDaily ==> liste de consommation quotidienne du chauffe-piscine à chaque jours (voir PuissanceDaily.time pour le pas de temps), pour débuggage
        self.SunHour ==> liste du nombre d'heure d'ensoleillement par jour (voir SunHour.time pour le pas en temps), pour débuggage
        self.DT ==> liste du delta de température en la Text moyenne quotidienne et la consigne (voir DT.time pour le pas en temps), pour débuggage

Hypothèses :    
-La consommation quotidienne est converti en consommation horaire selon le FU de la journée, en priorisant les heure avec un delta plus élevé
-Une puissance constante équivalent à la capacité thermique de la thermopompe en kW divisé par un COP de 4.5 est utilisé
-La consommation horaire de l'ensemble de la saison est décallé de quelueues minutes pour éviter le démarrage simuluté diversifié aux début des heures
-Période d'opération : De 3 jour après le démarrage de la pompe à 3 jour avant l'arrêt de la pompe (TPoolPump)
-Un COP de 4.5 est utilisé, en accord avec la recherche de N.Bigras "Piscine (et SPA) v020160209.docx"

@author: Simon Sansregret
"""

from stochastic_profile_generator.utils.master_equipment import MasterEquipment
import numpy as np
from stochastic_profile_generator.utils.data import Data
from datetime import timedelta, datetime
from random import random
import pandas as pd

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

class Tmaison_pool_heater:
    """Minimal container for pool heater simulation (matches chauffepiscine_test.ipynb pattern)"""

    def __init__(self):
        self.dt = None
        self.Donnees_Meteo = None
        self.Equis = {}  # Equipment dictionary

        # Create a mock pool pump object with required attributes (from chauffepiscine_test.ipynb)
        class MockPoolPump:
            def __init__(self):
                from datetime import datetime
                # Default pool season: May 1 to Octobre 10
                self.dtStartSeason = datetime(2015, 5, 1)
                self.dtEndSeason = datetime(2015, 10, 10)

        self.Equis['POOLPUMP_1'] = MockPoolPump()

class TChauffePiscine(MasterEquipment):
    # FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    # PROJECT_DIR = os.path.abspath(FILE_DIR + "/../")  # répertoire supérieur

    def configuration_ind(self):
        self.MINPERHOUR = 60
        self.HOURPERDAY = 24
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
        # Consigne
        PISC_CONSIGNE_Dict = {0 : np.random.uniform(low=19, high=36),#   'Aucun réponse',
                 1 : np.random.uniform(low=18, high=19),#'19 °C (66 °F) ou moins',
                 2 : np.random.uniform(low=20, high=22),#'20 à 21 °C (68 à 70 °F)',
                 3 : np.random.uniform(low=22, high=24),#'22 à 23 °C (72 à 74 °F)',
                 4 : np.random.uniform(low=24, high=26),#'24 à 25 °C (75 à 77 °F)' ,
                 5 : 27, #np.random.uniform(low=26, high=28),#'26 à 27 °C (79 à 81 °F)',
                 6 : np.random.uniform(low=28, high=30),#'28 à 29 °C (82 à 84 °F)',
                 7 : np.random.uniform(low=30, high=32),#'30 à 31 °C (86 à 88 °F)',
                 8 : np.random.uniform(low=32, high=34),#'32 à 33 °C (90 à 92 °F)',
                 9 : np.random.uniform(low=34, high=36),#'34 °C (92 °F) ou plus'
                 }
        if 'PISC_CONSIGNE' in self.params:   
            self.Tset = PISC_CONSIGNE_Dict[self.params['PISC_CONSIGNE']]
        else :
            self.Tset = np.random.uniform(low=19, high=36) #26.66 # 80°F
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
        #Toile
        PISC_TOILE_Dict = {0: True,#'Non applicable',
                           1: False,#'Non',
                           2: True}#'Oui'}

        if 'PISC_TOILE' in self.params:     
            self.boToile = PISC_TOILE_Dict[self.params['PISC_TOILE']]
        else:
            self.boToile = True
        #---------------------------------------------------------------------
        #dbSurface
        PISC_SURFACE_Dict = {0 : 1,#'Non applicable',
                             1 : np.random.uniform(low=16, high=20),#'Inf à 20 m² (16.4)', 
                             2 : np.random.uniform(low=20, high=28),#'20 m² =< x < 28 m² (23.7)',
                             3 : np.random.uniform(low=28, high=37),#'28 m² =< x < 37 m² (32.2)',
                             4 : np.random.uniform(low=37, high=47),#'37 m² =< x < 47 m² (42.0)',
                             5 : np.random.uniform(low=47, high=59),#'47 m² =< x < 59 m² (53.2)',
                             6 : np.random.uniform(low=59, high=72),#'59 m² =< x < 72 m² (65.0)',
                             7 : np.random.uniform(low=72, high=80)}#'Sup ou = à 72 m² (76.5)'}
        
        #SIMONV2 TEST
        PISC_SURFACE_Dict = {0 : 1,#'Non applicable',
                             1 : 24, #np.random.uniform(low=16, high=20),#'Inf à 20 m² (16.4)', 
                             2 : 42, #np.random.uniform(low=20, high=28),#'20 m² =< x < 28 m² (23.7)',
                             3 : 48, #np.random.uniform(low=28, high=37),#'28 m² =< x < 37 m² (32.2)',
                             4 : 60, #np.random.uniform(low=37, high=47),#'37 m² =< x < 47 m² (42.0)',
                             5 : np.random.uniform(low=47, high=59),#'47 m² =< x < 59 m² (53.2)',
                             6 : np.random.uniform(low=59, high=72),#'59 m² =< x < 72 m² (65.0)',
                             7 : np.random.uniform(low=72, high=80)}#'Sup ou = à 72 m² (76.5)'}
                
             
        if self.stTypePiscine == 'HT' :
            if 'PISC_SURFACE' in self.params :
                if self.params['PISC_SURFACE'] == 0:
                    self.dbSurface = np.pi * (21 /3.28)**2 / 4  # 21 pied
                else:
                    self.dbSurface = PISC_SURFACE_Dict[self.params['PISC_SURFACE']]
            else :
                self.dbSurface = np.pi * (21 /3.28)**2 / 4  # 21 pied
        else :
            if 'PISC_SURFACE' in self.params:
                if self.params['PISC_SURFACE'] == 0:
                    self.dbSurface = 42
                else:
                    self.dbSurface = PISC_SURFACE_Dict[self.params['PISC_SURFACE']]
            else:
                self.dbSurface = 42 # 42 m²
        #---------------------------------------------------------------------
         #Exposition
        PISC_EXPOSITION_Dict = {0	: True,#'Non applicable',
                                1	: True,#'Entièrement exposée au soleil',
                                2	: False}#'Partiellement ou pas exposée au soleil',
                
        if 'PISC_EXPOSITION' in self.params:     
            self.boExposition = PISC_EXPOSITION_Dict[self.params['PISC_EXPOSITION']]
        else:
            self.boExposition = True           
        #---------------------------------------------------------------------
        #Capacité thermique du chauffage
        
        PISC_CHAUFSIZE_Dict = {0	: 19.2*3.451,# 'Non applicable',
                          1	: 35,#'35kBTU',
                          2	: 55,#'55kBTU',
                          3 : 75,#'75kBTU',
                          4 : 100,#'100kBTU',
                          5 : 125,#'125kBTU',
                          6 : 150,#'150kBTU',
                          7 : 175,#'175kBTU',
                          8 : 200,#'200kBTU',
                          9 : 225,#'150kBTU',
                          10 : 100}#'100kBTU' Ne sais pas}

        if 'PISC_CHAUFSIZE' in self.params:     
            self.dbPoolKW = PISC_CHAUFSIZE_Dict[self.params['PISC_CHAUFSIZE']] / 3.451 # kbtu to kw
        else:
            if self.stTypePiscine == 'HT' :
                if self.dbSurface < 40 : #plus petit que diamètre de 24'
                    self.dbPoolKW  = 18  #62kBTU soit 18 kW
                else :
                    self.dbPoolKW  = 22  #76kBTU soit 22 kW
            else:               # creusée
                if self.dbSurface < 55 : #plus petit que 18' X 32'
                    self.dbPoolKW  = 31  #107kBTU soit 18 kW
                else :
                    self.dbPoolKW  = 38  #130kBTU soit 22 kW
        #---------------------------------------------------------------------
        #Type de chauffage

        PISC_CHAUFTYPE_Dict = {0 : 'Pas de piscine ext/creusée ou pas de réponse',
                               1 : 'Thermopompe',
                               2 : 'Gaz/Propane/Mazout',
                               3 : 'Electrique',
                               4 : 'Capteur solaire',
                               5 : 'Autre/Ne sait pas'}
        if 'PISC_CHAUFSIZE' in self.params: 
            self.Chauftype = PISC_CHAUFTYPE_Dict[self.params['PISC_CHAUFTYPE']]
        else:
            self.Chauftype = PISC_CHAUFTYPE_Dict[1]
       #---------------------------------------------------------------------
       # source d'énergie

       #---------------------------------------------------------------------
       # COP
       
       #---------------------------------------------------------------------
       
       

        # Période d'utilisation du chauffe-piscine               
        if 'POOLPUMP_1' in self.M.Equis : # juste pour l'execution de cette classe
            self.dtStartSeason = self.M.Equis['POOLPUMP_1'].dtStartSeason + timedelta(days=3)
            self.dtEndSeason = self.M.Equis['POOLPUMP_1'].dtEndSeason - timedelta(days=3)
        elif 'Pompe_piscine_1' in self.M.Equis : # pour Parc virtuel car on renome poolpump
            self.dtStartSeason = self.M.Equis['Pompe_piscine_1'].dtStartSeason + timedelta(days=3)
            self.dtEndSeason = self.M.Equis['Pompe_piscine_1'].dtEndSeason - timedelta(days=3)
        else:
            self.dtStartSeason = datetime(2000, 5, 1, 8)
            self.dtEndSeason  = datetime(2000, 10, 10, 8)
        
        # Correction de la température de consigne en mai et septembre    
        if self.boToile == True : #Hypothèse utilisé par N. Bigras dans l'évaluation avec enerpool : "_ Programme Piscine 2013 avec CommDocSCUE V2013-04-30 FINALE.xls"
            dbRedTset = 1.5
        else:
            dbRedTset = 2.5
        self.diTsetMois = {4:self.Tset - dbRedTset ,5:self.Tset - dbRedTset,6:self.Tset,7:self.Tset, 8:self.Tset, 9:self.Tset - dbRedTset, 10:self.Tset - dbRedTset }
        
        #Nombre de minute aléatoire écoulé dans l'heure entre -30 et 30 minutes (faire un offset pour éliminer le démarrage du chauffe-piscine au heures en diversifié)
        self.StartDelayed  = int(0.5 * self.MINPERHOUR - int(random() * self.MINPERHOUR))

        # Correction pour dimunier la consommation qui est 30 % trop élévé par rappoort au simulation EnerPool
        if self.boToile :
            self.cor = 0.75
        else :
            self.cor = 0.85
        self.boExposition = True
            
            
        #Évaluation des paramètre a et b
        liPARAM = []
        liColumns = ['TypePiscine','Toile','Exposition', 'a', 'b']
        liPARAM.append(['HT', True, True, 0.75, 0.40])
        liPARAM.append(['HT', True, False, 0.75, 0.25])
        liPARAM.append(['HT', False, True, 1.05, 0.5])
        liPARAM.append(['HT', False, False, 1.05, 0.25])
        liPARAM.append(['CR', True, True, 0.75, 0.40])
        liPARAM.append(['CR', True, False, 0.75, 0.25])
        liPARAM.append(['CR', False, True, 1.1, 0.50])
        liPARAM.append(['CR', False, False, 1.1, 0.25])
        dfPARAM = pd.DataFrame(liPARAM, columns = liColumns)
        f1 = dfPARAM.TypePiscine == self.stTypePiscine
        f2 = dfPARAM.Toile == self.boToile 
        f3 = dfPARAM.Exposition == self.boExposition
        self.a = dfPARAM.loc[f1 & f2 & f3,'a'].values[0] 
        self.b = dfPARAM.loc[f1 & f2 & f3,'b'].values[0] 
        

        
        #DataFrame des données météo
        diMeteo = {'Text' : self.M.Donnees_Meteo['DryBulb'].data, 'GHI' : self.M.Donnees_Meteo['GHI'].data}
        self.dfMeteo = pd.DataFrame(diMeteo, index = self.M.Donnees_Meteo['DryBulb'].time)
        self.dfMeteo['GHI'] = self.dfMeteo['GHI'] /3.6 # mettre en Wh/m² au lieu de kJ/m² (CWEC semble être en Wh/m² et météo SIMEB)

        
    def Get_data(self): 

        self.dbCOP = 4.5
        if self.Projection['Activer'] == True:
            self.Get_data_evolution(Annee=self.Projection['Annee'])
            
            self.dbCOP = self.dbCOP / self.Data_Evol['Efficacite']
                
    def Calcul_Daily(self):
        # Calul de l'énergie réquise quotidienne
        for k, ts in enumerate(self.time_daily): 
            self.dtStart = datetime(ts.year, self.dtStartSeason.month, self.dtStartSeason.day, self.dtStartSeason.hour, self.dtStartSeason.minute) 
            self.dtEnd = datetime(ts.year, self.dtEndSeason.month, self.dtEndSeason.day, self.dtStartSeason.hour, self.dtEndSeason.minute) 

            if (ts >= self.dtStart and ts <= self.dtEnd) :
                day = (ts - datetime(ts.year, 1, 1)).days + 1
                Max_sun_hours = -0.0004143 * day**2 + 0.1425 * day + 3.077 
                Idiffuse = -0.039 * day**2  + 13.33 * day + 102.73 
                Ibeam = -0.3391 * day**2 + 116.04 * day - 3479.7 
                Imeasured = self.dfMeteo.loc[ts.strftime("%Y-%m-%d"),'GHI'].mean() * self.HOURPERDAY
                fract_sun = min(1, max((Imeasured - 2 * Idiffuse) / Ibeam,0 ))
                sun_hours = Max_sun_hours * fract_sun
                Text = self.dfMeteo.loc[ts.strftime("%Y-%m-%d"),'Text'].mean()
                Tset = self.diTsetMois[ts.month]
                
                self.PuissanceDaily.data[k] = max(0,self.cor * (self.a * (Tset - Text) - self.b * (sun_hours)) * self.dbSurface)                               
                self.PuissanceDaily.data[k] = min(self.dbPoolKW * self.HOURPERDAY, self.PuissanceDaily.data[k])
                self.PuissanceDaily.data[k] = self.PuissanceDaily.data[k] / self.dbCOP
                self.SunHour.data[k] = sun_hours 
                self.DT.data[k] = (self.Tset - Text)
                
    def Calcul_all_Time(self): 
        # Répartir la consommation quotidienne en consommation horaire
        # Hypothèse : Un FU qutodien est calculé en fonction de la pouissance maximales de la thermopompe donnant le nombre d'heure d'opération par jour
        #             Les heures sont sélectionnés aléatoirement en priosant les heures ayant une plus faible température extérieures   
        dbElecPower = self.dbPoolKW / self.dbCOP
        dfPuissance = pd.DataFrame(self.Puissance.data, index = self.Puissance.time)
        for k, ts in enumerate(self.time_daily):  
            
            self.dtStart = datetime(ts.year, self.dtStartSeason.month, self.dtStartSeason.day, self.dtStartSeason.hour, self.dtStartSeason.minute) 
            self.dtEnd = datetime(ts.year, self.dtEndSeason.month, self.dtEndSeason.day, self.dtStartSeason.hour, self.dtEndSeason.minute) 

            
            if (ts >= self.dtStart and ts <= self.dtEnd) :  
                if round(self.PuissanceDaily.data[k]) >= round(dbElecPower * self.HOURPERDAY)  : # FU = 1
                    dfPuissance.loc[ts.strftime("%Y-%m-%d")] = dbElecPower
                elif self.PuissanceDaily.data[k] <= 0 :    # FU = 0
                    dfPuissance.loc[ts.strftime("%Y-%m-%d")] = 0
                else :
                    FU = self.PuissanceDaily.data[k] / (dbElecPower * self.HOURPERDAY)
                    NbHour = int(round(FU * 24))
                    arProfilT = self.dfMeteo.loc[ts.strftime("%Y-%m-%d"),'Text'].resample('1H').mean().values
                    arProfilDTNorm =  (self.diTsetMois[ts.month] - arProfilT) / np.max((self.diTsetMois[ts.month] - arProfilT ))
                    arProfilDTNorm = np.where(arProfilDTNorm > 0, arProfilDTNorm, 0)
                    arProfilDTNorm = arProfilDTNorm * np.random.rand(24)
                    arHourSelected = arProfilDTNorm.argsort()[-NbHour:]
                    f1 = dfPuissance.loc[ts.strftime("%Y-%m-%d")].index.hour.isin(arHourSelected)
                    #filtreDate = dfPuissance.index == ts.strftime("%Y-%m-%d")
                    
                    dfPuissance[0].loc[ts.strftime("%Y-%m-%d")].loc[f1] = dbElecPower *1000.0 #kw to W
                    
                    #dfPuissance.loc[ts.strftime("%Y-%m-%d")].loc[f1] = dbElecPower #pas très élégant mais j'ai essayé avec 
        self.Puissance.data = dfPuissance[0].tolist() #list(dfPuissance.values) 
        
        
        # Décaller le démarrage du chauffe piscine de quelques minutes pour éviter le démarrage simultané au début de l'heure
        # au pire, viens diminuer la consommation de 2 % (0.5 heure sur 24 heures) sur la journée
        intMinuteStep = (self.time_simu[1] - self.time_simu[0]).seconds//60
        intStepDelayed = self.StartDelayed//intMinuteStep
        if intStepDelayed > 0 :
            self.Puissance.data =  [0] * intStepDelayed + self.Puissance.data[:-intStepDelayed]
        else:
            intStepDelayed = -intStepDelayed
            self.Puissance.data =  self.Puissance.data[intStepDelayed: ] + [0] * intStepDelayed


    def Init(self):
        self.Puissance = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))
        self.Gain = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))
        self.EauChaude = Data(self.Type, '-', 0, self.time_simu, [0.0]*len(self.time_simu))

        self.time_daily = pd.date_range(start=self.time_simu[0], end=self.time_simu[-1], freq = '1D')
        self.time_daily = [pd.Timestamp(ele) for ele in self.time_daily]
        self.PuissanceDaily = Data(self.Type, '-', 0, self.time_daily, [0.0]*len(self.time_daily))
        self.SunHour = Data(self.Type, '-', 0, self.time_daily, [None]*len(self.time_daily)) #Pour debuggage
        self.DT= Data(self.Type, '-', 0, self.time_daily, [None]*len(self.time_daily))       #Pour debuggage


    def Calcul_Equipement(self, time_simu):  
        self.time_simu = time_simu  # x min, simulation parc
        self.Init()
        self.Init_ind()
        
        PISC_CHAUFTYPE_Dict = {0 : 'Pas de piscine ext/creusée ou pas de réponse',
                               1 : 'Thermopompe',
                               2 : 'Gaz/Propane/Mazout',
                               3 : 'Electrique',
                               4 : 'Capteur solaire',
                               5 : 'Autre/Ne sait pas'}
        if self.Chauftype in [PISC_CHAUFTYPE_Dict[1]]:#, PISC_CHAUFTYPE_Dict[3]]: # sinon puissance=0 car pas electrique
            self.Get_data()
            #if self.dtEnd < self.time_simu[0] or self.dtStart > self.time_simu[-1] : return
            self.Calcul_Daily()
            self.Calcul_all_Time()



# if __name__ == '__main__':
#     import matplotlib.pyplot as plt
#     import sys
#     path = __file__[:__file__.rfind('ParcVirtuel')-1]
#     sys.path.append(path)
#     from ParcVirtuel.Batiment.Batiment_v8 import TMaison
#     #from ParcVirtuel.Outils.LoadMeteoTXT import Meteo
#     from ParcVirtuel.Outils.LoadMeteoEPW import Meteo
    
#    # Instanciation de l'objet M     
#    Zone_geo = 24
#    diContr = {'Construction': 0, }
#    diParam = {'UA': 154.747227544,'Atot': 120, 'TypeMaison': 'BUN', 'Tarif_HQ': 'D', 'Dict_Calib': {'F_apply' : [1],'Tarif_HQ': ['defaut'], 'F_FGrd' : [0], 'F_SSol' : [2]} }
#    M = TMaison(Zone_geo = Zone_geo, ParametreInput = diParam, Contraintes = diContr)
#    
#    
#    # Initilisation de l'objet M => car en argument de l'objet ChauffePsicine pour obtenir les données météo
#    MeteoName = 'st-hubert_2018-10-10_101906_ascii.txt'
#    #MeteoName = 'qc.epw' pour fichier epw, modifier l'import LoadMeteoTXT par LoadMeteoEPW
#    #MeteoName = 'CAN_PQ_Montreal.Intl.AP.716270_CWEC.epw'
#    DateDebut = np.datetime64('2015-05-01T00:00:00')
#    DateFin = np.datetime64('2015-10-11T00:00:00')
#    TimeStep = '5T'
#    obMeteo = Meteo(MeteoName = MeteoName, DateDebut = DateDebut, DateFin = DateFin,TimeStep = TimeStep)
#    obMeteo.CalculMeteo()
#    grMeteo = obMeteo.Donnees_Meteo.Grp_data  
#    flDtSec = pd.to_timedelta(grMeteo['DryBulb'].time[0].freq).total_seconds() 
#    flDtHeure=flDtSec/3600 #En heure
#    M.Initialisation(grMeteo, flDtHeure)
#    
#    # Initialisation du vecte4ur temps passé en argument de l'objet TChauffePiscine
#    time_simu = pd.date_range(start=DateDebut, end=DateFin, freq = TimeStep).tolist()
#    #time_simu = [pd.Timestamp(ele) for ele in time_simu]
#
#    # Paramètre 
#    stTypePiscine = 'CR' # 'CR' : creusé ou ou 'HT' : Hors-terre
#    LiPoolDiameterHT = [15,18,21,24,27]
#    LiPoolLengthCR = [24,28,30,32,34,36]
#    LiPoolWidthCR = [12,14,16,18,20,22]
#    liCapBTU = ['35kBTU', '55kBTU', '75kBTU', '100kBTU', '125kBTU', '150kBTU', '175kBTU', '200kBTU', '225kBTU']
#    boToile = True
#    boExposition = True
#    dbTconsigne = 26
#    
#    Param = {'Type' : 'POOLHEATER', 'Tconsigne': dbTconsigne, 'TypePiscine': stTypePiscine, 'Toile' : boToile, 'Exposition' : boExposition, 
#             u'Capacité' : liCapBTU[3], 'PoolDiameter' : LiPoolDiameterHT[1], 'PoolLength' : LiPoolLengthCR[-1], 'PoolWidth' : LiPoolWidthCR[3] } 
#    
#    obPoolHeater = TChauffePiscine(M, Param) 
#    obPoolHeater.Calcul_Equipement(time_simu) # Pas besoin de passer en argument les profils d'occupation et d'activités, occ_profile, act_profile, --> #self.Equis[idEqui].Calcul_Equipement(occ_profile, act_profile, self.Donnees_Meteo['DryBulb'].time)
#
#    dbConsoTotal = np.sum(obPoolHeater.PuissanceDaily.data)
#    plt.close('all')    
#    fig, ax = plt.subplots()    
#    x = obPoolHeater.PuissanceDaily.time
#    y = obPoolHeater.PuissanceDaily.data
#    ax.plot(x,y, label = 'Pool heater daily (kWh/jour)')
#    ax.plot(x,obPoolHeater.SunHour.data, label = 'sun_hour (Heure)')
#    x = obPoolHeater.Puissance.time
#    y = obPoolHeater.Puissance.data
#    ax.plot(x,y, label = 'Pool heater (kW)')    
#    ax.plot(M.Donnees_Meteo['DryBulb'].time, M.Donnees_Meteo['DryBulb'].data, label = u'Text (°C)')
#    ax.legend(loc=1)
#    plt.show()


    # Comparaison avec les données de N. Bigras : "fichier Piscine (et SPA)
        # Changer     
        #   from ParcVirtuel.Outils.LoadMeteoTXT import Meteo
        # par
        #   from ParcVirtuel.Outils.LoadMeteoEPW import Meteo

        
    # PISC_PRESENCE_Dict = { 0 : 'Ménage ne possédant pas de piscine',
    #                        1 : 'Ménage possédant une piscine'}
    
    # PISC_TYPE_Dict = { 0 : 'Pas de piscine ext/creusée ou pas de réponse',
    #                1 : 'Extérieure – Creusée',
    #                2 : 'Extérieure – Hors terre'
    #                }

    # PISC_CHAUFFEE_Dict = { 0 : 'Pas de piscine ou piscine pas chauffé',
    #                        1 : 'Piscine Chauffée'}
    
    # PISC_CHAUFTYPE_Dict = { 
    #                0 : 'Pas de piscine ext/creusée ou pas de réponse',
    #                1 : 'Thermopompe',
    #                2 : 'Gaz/Propane/Mazout',
    #                3 : 'Electrique',
    #                4 : 'Capteur solaire',
    #                5 : 'Autre/Ne sait pas'
    #                }
    
    # PISC_CHAUFSIZE_Dict = { 
    #                   0	: 'Non applicable',
    #                   1	: '35kBTU',
    #                   2	: '55kBTU',
    #                   3 : '75kBTU',
    #                   4 : '100kBTU',
    #                   5 : '125kBTU',
    #                   6 : '150kBTU',
    #                   7 : '175kBTU',
    #                   8 : '200kBTU',
    #                   9 : '225kBTU',
    #                   10 : '100kBTU'}
    
    # PISC_MINUTERIE_Dict = { 
    #                   0	: 'Non applicable',
    #                   1	: 'Avec minuterie',
    #                   2	: 'Sans minuterie',
    #                   }
    
    # PISC_TOILE_Dict = { 
    #                   0	: 'Non applicable',
    #                   1	: 'Non',
    #                   2	: 'Oui',
    #                   }
    
    # PISC_EXPOSITION_Dict = { 
    #                   0	: 'Non applicable',
    #                   1	: 'Entièrement exposée au soleil',
    #                   2	: 'Partiellement ou pas exposée au soleil',
    #                   }
    
    # PISC_CONSIGNE_Dict = { 
    #                  0 : 'Aucun réponse',
    #                  1 : '19 °C (66 °F) ou moins',
    #                  2 : '20 à 21 °C (68 à 70 °F)',
    #                  3 : '22 à 23 °C (72 à 74 °F)',
    #                  4 : '24 à 25 °C (75 à 77 °F)' ,
    #                  5 : '26 à 27 °C (79 à 81 °F)',
    #                  6 : '28 à 29 °C (82 à 84 °F)',
    #                  7 : '30 à 31 °C (86 à 88 °F)',
    #                  8 : '32 à 33 °C (90 à 92 °F)',
    #                  9 : '34 °C (92 °F) ou plus'
    #                  }
    

    # PISC_SURFACE_Dict = { 
    #                      0 : 'Non applicable',
    #                      1 : 'Inf à 20 m² (16.4)', 
    #                      2 : '20 m² =< x < 28 m² (23.7)',
    #                      3 : '28 m² =< x < 37 m² (32.2)',
    #                      4 : '37 m² =< x < 47 m² (42.0)',
    #                      5 : '47 m² =< x < 59 m² (53.2)',
    #                      6 : '59 m² =< x < 72 m² (65.0)',
    #                      7 : 'Sup ou = à 72 m² (76.5)'
    #                      }
     
    # diParamPisc = {'Type' : 'POOLHEATER',
    #                'PISC_PRESENCE' : 1, #'Ménage possédant une piscine'
    #                'PISC_TYPE' : 1 , # 'Extérieure – Creusée
    #                'PISC_CHAUFFEE' : 1,  #'Piscine Chauffée'}
    #                'PISC_CHAUFTYPE' : 1,  #1 : 'Thermopompe',
    #                'PISC_CHAUFSIZE' : 10, # '100kBTU'
    #                'PISC_MINUTERIE' : 2,  # 'Sans minuterie'
    #                'PISC_TOILE' : 2, 	#: 'Oui',
    #                'PISC_EXPOSITION' : 1, #'Entièrement exposée au soleil',
    #                'PISC_CONSIGNE' : 5 , # 5 : '26 à 27 °C (79 à 81 °F)',
    #                'PISC_SURFACE' : 1 # 'Inf à 20 m² (16.4)',
    #                }
    
#    stTypePiscine = 'CR' # 'CR' : creusé ou ou 'HT' : Hors-terre
#    LiPoolDiameterHT = [15,18,21,24,27]
#    LiPoolLengthCR = [24,28,30,32,34,36]
#    LiPoolWidthCR = [12,14,16,18,20,22]
#    liCapBTU = ['35kBTU', '55kBTU', '75kBTU', '100kBTU', '125kBTU', '150kBTU', '175kBTU', '200kBTU', '225kBTU'  ]
#    boToile = False
#    boExposition = True
#    dbTconsigne = 27
    #Capacité de la thermopompe ( HT24m² : 62kBTU, HT42m² : 76kBTU, CR48m² : 107kBTU, CR60m²130kBTU
            
    # diCase = {'MTL_HT_15_ST' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 2, 'Surface' : 1, 'Toile' : 1, 'Cap' : 2 },
    #          'MTL_HT_18_ST' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 2, 'Surface' : 2,  'Toile' : 1, 'Cap' : 3 },
    #          'MTL_CR_48_ST' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 1, 'Surface' : 3,  'Toile' : 1, 'Cap' : 4 },
    #          'MTL_CR_60_ST' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 1, 'Surface' : 4,  'Toile' : 1, 'Cap' : 5 },
    #          'MTL_HT_15_AT' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 2, 'Surface' : 1,  'Toile' : 2, 'Cap' : 2 },
    #          'MTL_HT_18_AT' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 2, 'Surface' : 2,  'Toile' : 2, 'Cap' : 3 },
    #          'MTL_CR_48_AT' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 1, 'Surface' : 3,  'Toile' : 2, 'Cap' : 4 },
    #          'MTL_CR_60_AT' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 1, 'Surface' : 4,  'Toile' : 2, 'Cap' : 5 },
    #          'qc_HT_15_ST' : {'Meteo' : 'qc.epw', 'TypePiscine' : 2, 'Surface' : 1,  'Toile' : 1, 'Cap' : 2 },
    #          'qc_HT_18_ST' : {'Meteo' : 'qc.epw', 'TypePiscine' : 2, 'Surface' : 2,  'Toile' : 1, 'Cap' : 3 },
    #          'qc_CR_48_ST' : {'Meteo' : 'qc.epw', 'TypePiscine' : 1, 'Surface' : 3,  'Toile' : 1, 'Cap' : 4 },
    #          'qc_CR_60_ST' : {'Meteo' : 'qc.epw', 'TypePiscine' : 1, 'Surface' : 4,  'Toile' : 1, 'Cap' : 5 },
    #          'qc_HT_15_AT' : {'Meteo' : 'qc.epw', 'TypePiscine' : 2, 'Surface' : 1,  'Toile' : 2, 'Cap' : 2 },
    #          'qc_HT_18_AT' : {'Meteo' : 'qc.epw', 'TypePiscine' : 2, 'Surface' : 2,  'Toile' : 2, 'Cap' : 3 },
    #          'qc_CR_48_AT' : {'Meteo' : 'qc.epw', 'TypePiscine' : 1, 'Surface' : 3,  'Toile' : 2, 'Cap' : 4 },
    #          'qc_CR_60_AT' : {'Meteo' : 'qc.epw', 'TypePiscine' : 1, 'Surface' : 4,  'Toile' : 2, 'Cap' : 5 },
    #          'bag_HT_15_ST' : {'Meteo' : 'bag.epw', 'TypePiscine' : 2, 'Surface' : 1,  'Toile' : 1, 'Cap' : 2 },
    #          'bag_HT_18_ST' : {'Meteo' : 'bag.epw', 'TypePiscine' : 2, 'Surface' : 2,  'Toile' : 1, 'Cap' : 3 },
    #          'bag_CR_48_ST' : {'Meteo' : 'bag.epw', 'TypePiscine' : 1, 'Surface' : 3,  'Toile' : 1, 'Cap' : 4 },
    #          'bag_CR_60_ST' : {'Meteo' : 'bag.epw', 'TypePiscine' : 1, 'Surface' : 4,  'Toile' : 1, 'Cap' : 5 },
    #          'bag_HT_15_AT' : {'Meteo' : 'bag.epw', 'TypePiscine' : 2, 'Surface' : 1,  'Toile' : 2, 'Cap' : 2 },
    #          'bag_HT_18_AT' : {'Meteo' : 'bag.epw', 'TypePiscine' : 2, 'Surface' : 2,  'Toile' : 2, 'Cap' : 3 },
    #          'bag_CR_48_AT' : {'Meteo' : 'bag.epw', 'TypePiscine' : 1, 'Surface' : 3,  'Toile' : 2, 'Cap' : 4 },
    #          'bag_CR_60_AT' : {'Meteo' : 'bag.epw', 'TypePiscine' : 1, 'Surface' : 4,  'Toile' : 2, 'Cap' : 5 }}
    
    #diCase = {'MTL_HT_15_ST' : {'Meteo' : 'mtl.epw', 'TypePiscine' : 2, 'Surface' : 2, 'Toile' : 1, 'Cap' : 2 }}
#     diResult = {}
#     for cas in diCase  :
#                # Instanciation de l'objet M     
#             Zone_geo = 24
#             diContr = {'Construction': 0, }
#             diParam = {'UA': 154.747227544,'Atot': 120, 'TypeMaison': 'BUN', 'Tarif_HQ': 'D', 'Dict_Calib': {'F_apply' : [1],'Tarif_HQ': ['defaut'], 'F_FGrd' : [0], 'F_SSol' : [2]} }
#             M = TMaison(Zone_geo = Zone_geo, ParametreInput = diParam, Contraintes = diContr)
            
            
#             # Initilisation de l'objet M => car en argument de l'objet ChauffePsicine pour obtenir les données météo
#             MeteoName = diCase[cas]['Meteo']
#             DateDebut = np.datetime64('2015-05-01T00:00:00')
#             DateFin = np.datetime64('2015-09-30T00:00:00')
#             TimeStep = '5T'
#             obMeteo = Meteo(MeteoName = MeteoName, DateDebut = DateDebut, DateFin = DateFin,TimeStep = TimeStep)
#             obMeteo.CalculMeteo()
#             grMeteo = obMeteo.Donnees_Meteo.Grp_data  
#             flDtSec = pd.to_timedelta(grMeteo['DryBulb'].time[0].freq).total_seconds() 
#             flDtHeure=flDtSec/3600 #En heure
#             M.Initialisation(grMeteo, flDtHeure)
                   
#             time_simu = pd.date_range(start=DateDebut, end=DateFin, freq = TimeStep).tolist()
#             time_simu = [pd.Timestamp(ele) for ele in time_simu]
           
#             diParamPisc['PISC_TYPE'] = diCase[cas]['TypePiscine']
#             diParamPisc['PISC_SURFACE'] = diCase[cas]['Surface']
#             diParamPisc['PISC_TOILE'] = diCase[cas]['Toile']        
#             diParamPisc['PISC_CHAUFSIZE'] = diCase[cas]['Cap'] 
                    
# #            Param = {'Type' : 'POOLHEATER', 'Tconsigne': dbTconsigne, 'TypePiscine': diCase[cas]['TypePiscine'], 'Toile' : diCase[cas]['Toile'], 'Exposition' : boExposition, 
# #                    'PoolDiameter' : diCase[cas]['Dia'], 'PoolLength' : diCase[cas]['Longueur'], 'PoolWidth' : diCase[cas]['Largeur'] } 
# #            #Param[u'Capacité'] = liCapBTU[5]
            
#             obPoolHeater = TChauffePiscine(M, diParamPisc) 
#             obPoolHeater.Calcul_Equipement(time_simu) 
    
#             diResult[cas] = int(np.sum(obPoolHeater.PuissanceDaily.data))
   