# -*- coding: utf-8 -*-
"""

@author: Francois Laurencelle, Brice Le Lostec, Simon Sansregret, Benoit Delcroix
"""
# Libraries
import numpy as np
from datetime import timedelta, datetime
from random import random
import pandas as pd

# Local libraries
from stochastic_profile_generator.utils.data import Data
from stochastic_profile_generator.utils.master_equipment import MasterEquipment

class Tsetpoint(MasterEquipment):
    
    def configuration_ind(self):
        """
        Initialise la classe avec les paramètres utilisateur.
        """

        self.h1 = self.get_params('Tconsignes_chauffage_H1')
        self.h2 = self.get_params('Tconsignes_chauffage_H2')
        self.h3 = self.get_params('Tconsignes_chauffage_H3')
        self.h4 = self.get_params('Tconsignes_chauffage_H4')

        self.Temp_cons = {  #'Climatisation' : self.get_params('Tclim'),
                            #'Garage': self.get_params('Tgarage'),
                            ##'Innocupe': self.get_params('Tinnocupe'),
                            ##'Sous_sol_Vide_sanitaire': self.get_params('Tsoussol'),
                            ##'Absence': self.get_params('Tabsence'),
                            'Tjour': self.get_params('Heating Setpoint')[0],
                            'Tsoir': self.get_params('Heating Setpoint')[1],
                            'Tnuit': self.get_params('Heating Setpoint')[2],
                            'Tmatin': self.get_params('Heating Setpoint')[1]#hypothèse : Tmatin = Tsoir
                            }

        #self.mode_setback = self.get_params('mode_setback')

    def get_params(self, att):
        if att not in self.params:
            raise AttributeError(f"Paramètre '{att}' non trouvé dans les paramètres.")
        else:
            if att == 'Heating Setpoint':
                if isinstance(eval(self.params[att]), (list, tuple)):
                    if len(eval(self.params[att])) == 3:
                        return eval(self.params[att])
                    else:
                        raise ValueError("Le paramètre 'Heating Setpoint' doit être une liste ou un tuple de trois valeurs : [Tjour, Tsoir, Tnuit].")                      
                else:
                    raise ValueError("Le paramètre 'Heating Setpoint' doit être une liste ou un tuple de trois valeurs : [Tjour, Tsoir, Tnuit].")
            else:
                return self.params[att]

    def Calcul_consignes(self, ts_list):
        """
        Calcule le profil de setback (Tnuit, Tjour, Tmatin, Tsoir) pour chaque pas de temps.
            la colonne 'Tconsigne' du dataframe self.Tconsigne contient :
                - Tnuit : consigne de température de nuit
                - Tjour : consigne de température de jour
                - Tmatin : consigne de température de matin
                - Tsoir : consigne de température de soir
            
            remarque : Il y a un mélange de style entre le code de Francois et le mien
            pour les heures notemment. j'ai ajouté un dataframe pour faciliter le debugage et les opérations de filtrage
            Devrait etre amélioré au niveau des heures (devrait ressembler à la méthode consignes_TDT)
            
            jour et nuit (temperature)
                           ___TM____              ___TS____                  
                          |         |            |         |                 
              0h___TN___h1|       h2|____TJ____h3|       h4|___TN_____24h    
                

            Nuit (temperature)
                           __TM_________TJ___________TS____                  
                          |                                |
              0h___TN __h1|       h2           h3        h4|___TN______24h    
              
        """
        self.time_simu = ts_list

        ts = pd.to_datetime(ts_list)
        self.Tconsigne = pd.DataFrame(index=ts, columns=['Heure', 'dayofweek', 'Pconsigne_Chauffage', "Tconsigne_Chauffage"])
        self.Tconsigne['Heure'] = ts.hour + ts.minute / 60
        self.Tconsigne['dayofweek'] = ts.dayofweek

        # Création des filtres horaires
        filtre_Tnuit = (self.Tconsigne['Heure'] < self.h1) | (self.Tconsigne['Heure'] >= self.h4)
        filtre_Tjour = (self.Tconsigne['Heure'] >= self.h2) & (self.Tconsigne['Heure'] < self.h3)
        filtre_Tmatin = (self.Tconsigne['Heure'] >= self.h1) & (self.Tconsigne['Heure'] < self.h2)
        filtre_Tsoir = (self.Tconsigne['Heure'] >= self.h3) & (self.Tconsigne['Heure'] < self.h4)
 
        # Création des filtres jour/semaine

        # Attribution des profils de consigne
        self.Tconsigne.loc[filtre_Tnuit, 'Pconsigne_Chauffage'] = 'Tnuit'
        self.Tconsigne.loc[filtre_Tjour, 'Pconsigne_Chauffage'] = 'Tjour'
        self.Tconsigne.loc[filtre_Tmatin, 'Pconsigne_Chauffage'] = 'Tmatin'
        self.Tconsigne.loc[filtre_Tsoir, 'Pconsigne_Chauffage'] = 'Tsoir'
        # Pas de changement de consigne le weekend
        self.Tconsigne.loc[filtre_Tnuit, 'Tconsigne_Chauffage'] = self.Temp_cons['Tnuit']
        self.Tconsigne.loc[filtre_Tjour, 'Tconsigne_Chauffage'] = self.Temp_cons['Tjour']
        self.Tconsigne.loc[filtre_Tmatin, 'Tconsigne_Chauffage'] = self.Temp_cons['Tmatin']
        self.Tconsigne.loc[filtre_Tsoir, 'Tconsigne_Chauffage'] = self.Temp_cons['Tsoir']

    def get_Tconsigne_Chauffage(self):
        """
        Retourne le profil de température de consigne de chauffage.
        """
        Tcons = self.Tconsigne['Tconsigne_Chauffage'].tolist()
        return Tcons

    def get_Pconsigne_Chauffage(self):
        """
        Retourne le profil de mode de consigne de chauffage.
        """
        Pcons = self.Tconsigne['Pconsigne_Chauffage'].tolist()
        return Pcons

    def get_Time(self):
        """
        Retourne le profil temporel de la simulation.
        """
        return self.Tconsigne.index.tolist()

    def Calcul_Equipement(self, time_simu):  
        self.Init_ind() # initialisation personifiée
        self.Calcul_consignes(time_simu)
        
        #Tc = self.get_Tconsigne_Chauffage()
        #Pc = self.get_Pconsigne_Chauffage()
        #Time = self.time_simu

        #return Time, Tc, Pc

if __name__ == '__main__':
    
    ts=pd.date_range(start='2015-01-04',end='2015-01-10',freq='min')
    ParametreInput = {'Tarif_HQ': 'D'}  # D ou TDT
    
    Tconstemp = TConsignes(params = ParametreInput)
    Tconstemp.Calcul_consignes(ts)  # True : Temperature de confort, False : temperature de recul
    Tconstemp.allocate_Temperature()
    plt.figure(figsize=(10,5))
    
    plt.plot(Tconstemp.Tconsigne.index,Tconstemp.Trcons, label='Tarif D')
    
    plt.xlabel('Date/Heure')
    plt.ylabel('Température consigne (°C)')
    plt.title('Profil de température de consigne')
    plt.legend()
    plt.tight_layout()
    # Affiche la figure (nécessaire hors environnement interactif)
    try:
        plt.show()
    except Exception:
        # En cas d'environnement sans affichage (ex: batch), on sauve le graphique
        if False:
            out_path = os.path.join(TConsignes.FILE_DIR, 'profil_consigne.png')
            plt.savefig(out_path)
            print(f"Figure sauvegardée: {out_path}")
    print(Tconstemp.setBack)