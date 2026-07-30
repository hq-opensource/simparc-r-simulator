from postprocess.prism import Prism
import time
import pandas as pd

import sys
import warnings

warnings.simplefilter('ignore')

class Quantite_interet_description():
    dict_description = {
        "Conso_annuelle_electricite" : {"Description": "La consommation annuelle d’électricité",
                                        "Unité": "kWh"},
        "Conso_annuelle_gaz" : {"Description": "La consommation annuelle de gaz",
                                "Unité": "kWh ou m³"},
        "Conso_annuelle_mazout" : {"Description": "La consommation annuelle de mazout",
                                   "Unité": "kWh ou m³"},
        "Conso_annuelle_bois_granules" : {"Description": "La consommation annuelle de bois ou granules",
                                          "Unité": "kWh"},
        "Conso_base_electricite" : {"Description": "La consommation électrique de base journalière (journées où la température moyenne journalière est entre 8 et 15°C)",
                                    "Unité": "kWh/jour"},
        "Pente_chauffage_electricite" : {"Description": "La pente de chauffage (électricité) (journées où la température moyenne journalière est ≤ 8°C) (profil électrique)",
                                         "Unité": "W/K"},
        "Pente_climatisation_electricite" : {"Description": "La pente de climatisation (électricité) (journées où la température moyenne journalière est ≥ 15°C) (profil électrique) ",
                                             "Unité": "W/K"},
        "Pente_chauffage_gaz" : {"Description": "La pente de chauffage (gaz – si des données mensuelles sont disponibles)",
                                 "Unité": "W/K"},
        "Pointe_hiver_am" : {"Description": "La pointe électrique d’hiver du matin, soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≤ 8°C;",
                             "Unité": "kW"},
        "Pointe_h_hiver_am" : {"Description": "L’heure de la pointe électrique d’hiver du matin (valeur entière entre 0 et 11, inclusivement) – à évaluer par rapport au profil moyen d’hiver;",
                               "Unité": "h"},
        "Pointe_hiver_pm" : {"Description": "La pointe électrique d’hiver du soir, soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≤ 8°C",
                             "Unité": "kW"},
        "Pointe_h_hiver_pm" : {"Description": "L’heure de la pointe électrique d’hiver du soir (valeur entière entre 12 et 23, inclusivement) – à évaluer par rapport au profil moyen d’hiver",
                               "Unité": "h"},
        "Pointe_ete_am" : {"Description": "La pointe électrique d’été du matin, soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≥ 15°C)",
                           "Unité": "kW"},
        "Pointe_h_ete_am" : {"Description": "L’heure de la pointe électrique d’été du matin (valeur entière entre 0 et 11, inclusivement) – à évaluer par rapport au profil moyen d’été", 
                             "Unité": "h"},
        "Pointe_ete_pm" : {"Description": "La pointe électrique d’été du soir, soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≥ 15°C)",
                           "Unité": "kW"},
        "Pointe_h_ete_pm" : {"Description": "L’heure de la pointe électrique d’été du soir (valeur entière entre 12 et 23, inclusivement) – à évaluer par rapport au profil moyen d’été",
                             "Unité": "h"},
        "EcartType_Quotidien_hiver" : {"Description": "L’écart-type journalier moyen de la consommation électrique durant les journées d’hiver où la température moyenne journalière est ≤ 8°C (idéalement pour des pas de temps de maximum 1h)",
                                       "Unité": "kWh"},
        "EcartType_Quotidien_ete" : {"Description": "L’écart-type journalier moyen de la consommation électrique durant les journées d’été où la température moyenne journalière est ≥ 15°C (idéalement pour des pas de temps de maximum 1h)",
                                     "Unité": "kWh"},
        "EcartType_Quotidien_misaison" : {"Description": "L’écart-type journalier moyen de la consommation électrique durant les journées de misaison où la température moyenne journalière est entre 8 et 15°C (idéalement pour des pas de temps de maximum 1h)",
                                          "Unité": "kWh"},
        "FU_Quotidien_hiver" : {"Description": "Le facteur d’utilisation en période hivernale où la température moyenne journalière est ≤ 8°C. Le facteur d’utilisation est le rapport entre la consommation électrique moyenne d’un pas de temps et la consommation électrique maximale d’un pas de temps. Idéalement, le pas de temps est de maximum 1h.",
                                "Unité": "-"},
        "FU_Quotidien_ete" : {"Description": "Le facteur d’utilisation en période estivale où la température moyenne journalière est ≥ 15°C",
                              "Unité": "-"},
        "FU_Quotidien_misaison" : {"Description": "Le facteur d’utilisation durant la mi-saison où la température moyenne journalière est entre 8 et 15°C",
                                   "Unité": "-"},
        "RatioJN_Quotidien_hiver" : {"Description": "Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant les journées d’hiver où la température moyenne journalière est ≤ 8°C",
                                     "Unité": "-"},
        "RatioJN_Quotidien_ete" : {"Description": "Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant les journées d’été où la température moyenne journalière est ≥ 15°C",
                                   "Unité": "-"},
        "RatioJN_Quotidien_misaison" : {"Description": "Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant la misaison où la température moyenne journalière est entre 8 et 15°C",
                                        "Unité": "-"},
    }

def Quantite_interet(pd_Alldata_id):
    #'Time_Unnamed: 0_level_1',
    # 'TimeUTC_Unnamed: 1_level_1',
     #  'Energy Use: Total_kBtu', 'Energy Use: Net_kBtu',
     #  'Fuel Use: Electricity: Total_kWh', 'Fuel Use: Electricity: Net_kWh',
     #  'End Use: Electricity: Heating_kWh',
     #  'End Use: Electricity: Heating Fans/Pumps_kWh',
     #  'End Use: Electricity: Cooling_kWh',
     #  'End Use: Electricity: Cooling Fans/Pumps_kWh',
     #  'End Use: Electricity: Hot Water_kWh',
     #  'End Use: Electricity: Lighting Interior_kWh',
     #  'End Use: Electricity: Lighting Exterior_kWh',
     #  'End Use: Electricity: Mech Vent_kWh',
     #  'End Use: Electricity: Refrigerator_kWh',
     #  'End Use: Electricity: Freezer_kWh',
     #  'End Use: Electricity: Dishwasher_kWh',
     #  'End Use: Electricity: Range/Oven_kWh',
     #  'End Use: Electricity: Ceiling Fan_kWh',
     #  'End Use: Electricity: Television_kWh',
     #  'End Use: Electricity: Plug Loads_kWh', 
     # ...
     #  'Temperature: Attic - Vented_F',
     #  'Temperature: Conditioned Space_F', 'Temperature: Heating Setpoint_F',
     #  'Temperature: Cooling Setpoint_F', 'Weather: Drybulb Temperature_F',
     #  'Weather: Wetbulb Temperature_F', 'Weather: Relative Humidity_%',
     #  'Weather: Wind Speed_mph',
     #  'Weather: Diffuse Solar Radiation_Btu/(hr*ft^2)',
     #  'Weather: Direct Solar Radiation_Btu/(hr*ft^2)'],

    col_weather_temperature_F = "Weather: Drybulb Temperature_F" # °F
    col_electricity_use = "Fuel Use: Electricity: Total_kWh" #kWh on timestep
    col_time_local = "Time"
    col_time_utc = "TimeUTC"

    #convert Time columns to datetime
    pd_Alldata_id[col_time_local] = pd.to_datetime(pd_Alldata_id[col_time_local])
    pd_Alldata_id[col_time_utc] = pd.to_datetime(pd_Alldata_id[col_time_utc])

    pd_Alldata_id["Jourlocal"] = pd_Alldata_id[col_time_local].dt.date
    pd_Alldata_id["Heurelocal"] = pd_Alldata_id[col_time_local].dt.hour
    
    # Convert °F to °C
    col_weather_temperature_C = "Weather: Drybulb Temperature_C"
    pd_Alldata_id[col_weather_temperature_C] = (pd_Alldata_id[col_weather_temperature_F] - 32) * 5.0/9.0

    # 
    #Analyse Prism
    pd_Alldata_id_Quo = pd_Alldata_id.groupby(pd_Alldata_id[col_time_local].dt.date).agg({col_electricity_use: 'sum',
                                                                                          col_weather_temperature_C: 'mean'})\
                                                                                            .reset_index()
    list_P = pd_Alldata_id_Quo[col_electricity_use].to_list()#somme quotidienne de l'energie active livrée
    list_T = pd_Alldata_id_Quo[col_weather_temperature_C].to_list()#moyenne quotidienne de la température au 15 minutes (Note : données sources sont horaires)

    InstClsPrism = Prism(QuotikWh = list_P, QuotiTemp = list_T)
    res = InstClsPrism.calcul()
    #print(InstClsPrism.param) #dict résultats
    #InstClsPrism.trace() #trace le graphique

    dict_caracteristiques = {}

    '''
    La liste suggérée de ces quantités d’intérêt adresse les caractéristiques :
    
    - Des données annuelles :
    (1) La consommation annuelle d’électricité [kWh];
    (2) La consommation annuelle de gaz [kWh ou m³];
    (3) La consommation annuelle de mazout [kWh ou m³];
    (4) La consommation annuelle de bois ou granules [kWh];
    (5) La consommation électrique de base journalière [kWh/jour] (journées où la température moyenne journalière est entre 8 et 15°C) – voir Figure 1;
    (6) La pente de chauffage (électricité) [W/K] (journées où la température moyenne journalière est ≤ 8°C) (profil électrique) – voir Figure 1;
    (7) La pente de climatisation (électricité) [W/K] (journées où la température moyenne journalière est ≥ 15°C) (profil électrique) – voir Figure 1;
    (8) La pente de chauffage (gaz – si des données mensuelles sont disponibles) [W/K] – voir Figure 2;
    
    
    - Du profil de charge électrique :
    (9) La pointe électrique d’hiver du matin [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≤ 8°C;
    (10) L’heure de la pointe électrique d’hiver du matin (valeur entière entre 0 et 11, inclusivement) – à évaluer par rapport au profil moyen d’hiver;
    (11) La pointe électrique d’hiver du soir [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≤ 8°C;
    (12) L’heure de la pointe électrique d’hiver du soir (valeur entière entre 12 et 23, inclusivement) – à évaluer par rapport au profil moyen d’hiver;
    (13) La pointe électrique d’été du matin [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≥ 15°C);
    (14) L’heure de la pointe électrique d’été du matin (valeur entière entre 0 et 11, inclusivement) – à évaluer par rapport au profil moyen d’été;
    (15) La pointe électrique d’été du soir [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≥ 15°C);
    (16) L’heure de la pointe électrique d’été du soir (valeur entière entre 12 et 23, inclusivement) – à évaluer par rapport au profil moyen d’été;
    (17) L’écart-type journalier moyen de la consommation électrique durant les journées d’hiver où la température moyenne journalière est ≤ 8°C [kWh] (idéalement pour des pas de temps de maximum 1h);
    (18) L’écart-type journalier moyen de la consommation électrique durant les journées d’été où la température moyenne journalière est ≥ 15°C [kWh] (idéalement pour des pas de temps de maximum 1h);
    (19) L’écart-type journalier moyen de la consommation électrique durant les journées de misaison où la température moyenne journalière est entre 8 et 15°C [kWh] (idéalement pour des pas de temps de maximum 1h);
    (20) Le facteur d’utilisation en période hivernale où la température moyenne journalière est ≤ 8°C [%]. Le facteur d’utilisation est le rapport entre la consommation électrique moyenne d’un pas de temps et la consommation électrique maximale d’un pas de temps. Idéalement, le pas de temps est de maximum 1h.
    (21) Le facteur d’utilisation en période estivale où la température moyenne journalière est ≥ 15°C [%];
    (22) Le facteur d’utilisation durant la mi-saison où la température moyenne journalière est entre 8 et 15°C [%];
    (23) Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant les journées d’hiver où la température moyenne journalière est ≤ 8°C [-];
    (24) Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant les journées d’été où la température moyenne journalière est ≥ 15°C [-];
    (25) Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant la misaison où la température moyenne journalière est entre 8 et 15°C [-].

    '''
    #données des jours d'hiver
    filter_h_T = (pd_Alldata_id_Quo[col_weather_temperature_C] <= 8)
    tempopd_Alldata_id_Quo_h = pd_Alldata_id_Quo[filter_h_T][[col_time_local]].drop_duplicates()
    tempopd_Alldata_id_Quo_h = tempopd_Alldata_id_Quo_h.rename(columns={col_time_local: "Jourlocal"})

    filter_h_d = ((pd_Alldata_id[col_time_local].dt.month >= 12) | (pd_Alldata_id[col_time_local].dt.month  <= 4))
    tempo_pd_Alldata_id_h = pd_Alldata_id[filter_h_d]


    pd_Alldata_id_h = pd.merge(tempo_pd_Alldata_id_h, tempopd_Alldata_id_Quo_h, on="Jourlocal", how='inner').reset_index()
    
    #données des jours d'été
    filter_e_T = (pd_Alldata_id_Quo[col_weather_temperature_C] >= 15)
    tempopd_Alldata_id_Quo_e = pd_Alldata_id_Quo[filter_e_T][[col_time_local]].drop_duplicates()
    tempopd_Alldata_id_Quo_e = tempopd_Alldata_id_Quo_e.rename(columns={col_time_local: "Jourlocal"})

    filter_e_d = ((pd_Alldata_id[col_time_local].dt.month >= 5) & (pd_Alldata_id[col_time_local].dt.month  <= 11))
    tempo_pd_Alldata_id_e = pd_Alldata_id[filter_e_d]

    pd_Alldata_id_e = pd.merge(tempo_pd_Alldata_id_e, tempopd_Alldata_id_Quo_e, on="Jourlocal", how='inner').reset_index()
    
    #données des jours de mi-saison
    filter_ms_T = (pd_Alldata_id_Quo[col_weather_temperature_C] > 8) & (pd_Alldata_id_Quo[col_weather_temperature_C] < 15)
    tempopd_Alldata_id_Quo_ms = pd_Alldata_id_Quo[filter_ms_T][[col_time_local]].drop_duplicates()
    tempopd_Alldata_id_Quo_ms = tempopd_Alldata_id_Quo_ms.rename(columns={col_time_local: "Jourlocal"})

    filter_ms_d = ((pd_Alldata_id[col_time_local].dt.month >= 4) & (pd_Alldata_id[col_time_local].dt.month  <= 6))\
                    | ((pd_Alldata_id[col_time_local].dt.month >= 9) & (pd_Alldata_id[col_time_local].dt.month  <= 10))
    tempo_pd_Alldata_id_ms = pd_Alldata_id[filter_ms_d]

    pd_Alldata_id_ms = pd.merge(tempo_pd_Alldata_id_ms, tempopd_Alldata_id_Quo_ms, on="Jourlocal", how='inner').reset_index()

    #_______________________________
    #(1) La consommation annuelle d’électricité [kWh];
    try:
        dict_caracteristiques["Conso_annuelle_electricite"] = pd_Alldata_id_Quo[col_electricity_use].sum() #kwh
    except:
        dict_caracteristiques["Conso_annuelle_electricite"] = None
    #_______________________________
    #(2) La consommation annuelle de gaz [kWh ou m³];
    dict_caracteristiques["Conso_annuelle_gaz"] = None
    
    #_______________________________
    #(3) La consommation annuelle de mazout [kWh ou m³];
    dict_caracteristiques["Conso_annuelle_mazout"] = None
    
    #_______________________________
    #(4) La consommation annuelle de bois ou granules [kWh];
    dict_caracteristiques["Conso_annuelle_bois_granules"] = None
    
    #_______________________________
    #(5) La consommation électrique de base journalière [kWh/jour] (journées où la température moyenne journalière est entre 8 et 15°C) – voir Figure 1;
    #filter_5 = (pd_Alldata_id_Quo[col_weather_temperature_C] >= 8) & (pd_Alldata_id_Quo[col_weather_temperature_C] <= 15)
    #dict_caracteristiques["Conso_base_electricite"] = pd_Alldata_id_Quo[filter_5][col_electricity_use].mean()# [kWh/jour]
    dict_caracteristiques["Conso_base_electricite"] = InstClsPrism.param["Base [kW]"]
    
    #_______________________________
    #(6) La pente de chauffage (électricité) [W/K] (journées où la température moyenne journalière est ≤ 8°C) (profil électrique) – voir Figure 1;
    #filter_6 = (pd_Alldata_id_Quo[col_weather_temperature_C] <= 8)
    #dict_caracteristiques["Pente_chauffage_electricite"] = sm.WLS( pd_Alldata_id_Quo[filter_6][col_electricity_use]/24*1000,
    #                                                               sm.tools.add_constant(pd_Alldata_id_Quo[filter_6][col_weather_temperature_C]))\
    #                                                            .fit()\
    #                                                            .params[1]
    dict_caracteristiques["Pente_chauffage_electricite"] = InstClsPrism.param["kch [W/°C]"]
    
    #_______________________________
    #(7) La pente de climatisation (électricité) [W/K] (journées où la température moyenne journalière est ≥ 15°C) (profil électrique) – voir Figure 1;
    dict_caracteristiques["Pente_climatisation_electricite"] = InstClsPrism.param["kcl [W/°C]"]
    
    #_______________________________
    #(8) La pente de chauffage (gaz – si des données mensuelles sont disponibles) [W/K] – voir Figure 2;
    dict_caracteristiques["Pente_chauffage_gaz"] = None
    
    #_______________________________
    #(9) La pointe électrique d’hiver du matin [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≤ 8°C;
    #filtrage des données quotidiennes en fonction de la température extérieure
    tempo_pd_Alldata_id = pd_Alldata_id_h[pd_Alldata_id_h["Heurelocal"]<=11].reset_index()

    #Sélection du la valeur la plus élevée
    try:
        dict_caracteristiques["Pointe_hiver_am"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()][col_electricity_use] * 4 # [kWh/15min] to kW
    except:
        dict_caracteristiques["Pointe_hiver_am"] = None
    #_______________________________
    #(10) L’heure de la pointe électrique d’hiver du matin (valeur entière entre 0 et 11, inclusivement) – à évaluer par rapport au profil moyen d’hiver;
    try:
        dict_caracteristiques["Pointe_h_hiver_am"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()]["Heurelocal"]
    except:
        dict_caracteristiques["Pointe_h_hiver_am"] = None
    #_______________________________
    #(11) La pointe électrique d’hiver du soir [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≤ 8°C;
    tempo_pd_Alldata_id = pd_Alldata_id_h[pd_Alldata_id_h["Heurelocal"]>=12].reset_index()
    try:
        dict_caracteristiques["Pointe_hiver_pm"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()][col_electricity_use] * 4 # [kWh/15min] to kW
    except:
        dict_caracteristiques["Pointe_hiver_pm"] = None
    #_______________________________       
    #(12) L’heure de la pointe électrique d’hiver du soir (valeur entière entre 12 et 23, inclusivement) – à évaluer par rapport au profil moyen d’hiver;
    try:
        dict_caracteristiques["Pointe_h_hiver_pm"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()]["Heurelocal"]
    except:
        dict_caracteristiques["Pointe_h_hiver_pm"] = None

    #_______________________________       
    #(13) La pointe électrique d’été du matin [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≥ 15°C);
    tempo_pd_Alldata_id = pd_Alldata_id_e[pd_Alldata_id_e["Heurelocal"]<=11].reset_index()
    try:
        dict_caracteristiques["Pointe_ete_am"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()][col_electricity_use] * 4 # [kWh/15min] to kW
    except:
        dict_caracteristiques["Pointe_ete_am"] = None      
    #_______________________________
    #(14) L’heure de la pointe électrique d’été du matin (valeur entière entre 0 et 11, inclusivement) – à évaluer par rapport au profil moyen d’été;
    try:
        dict_caracteristiques["Pointe_h_ete_am"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()]["Heurelocal"]
    except:
        dict_caracteristiques["Pointe_h_ete_am"] = None
    #_______________________________
    #(15) La pointe électrique d’été du soir [kW], soit la valeur maximale de puissance moyenne appelée durant un pas de temps (idéalement de maximum 1h) pendant des journées où la température moyenne journalière est ≥ 15°C);
    tempo_pd_Alldata_id = pd_Alldata_id_e[pd_Alldata_id_e["Heurelocal"]>=12].reset_index()
    
    try:
        dict_caracteristiques["Pointe_ete_pm"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()][col_electricity_use] * 4 # [kWh/15min] to kW
    except:
        dict_caracteristiques["Pointe_ete_pm"] = None
    #_______________________________
    #(16) L’heure de la pointe électrique d’été du soir (valeur entière entre 12 et 23, inclusivement) – à évaluer par rapport au profil moyen d’été;
    try:
        dict_caracteristiques["Pointe_h_ete_pm"] = tempo_pd_Alldata_id.iloc[tempo_pd_Alldata_id[col_electricity_use].idxmax()]["Heurelocal"]
    except:
        dict_caracteristiques["Pointe_h_ete_pm"] = None       
    #_______________________________        
    #(17) L’écart-type journalier moyen de la consommation électrique durant les journées d’hiver où la température moyenne journalière est ≤ 8°C [kWh] (idéalement pour des pas de temps de maximum 1h);
    
    #calcul de l'écart-type par jour puis moyenne des valeurs (kWh/15min)
    try:
        dict_caracteristiques["EcartType_Quotidien_hiver"] = pd_Alldata_id_h[["Jourlocal", col_electricity_use]].groupby("Jourlocal").std()[col_electricity_use].mean()
    except:
        dict_caracteristiques["EcartType_Quotidien_hiver"] = None
    #_______________________________  
    #(18) L’écart-type journalier moyen de la consommation électrique durant les journées d’été où la température moyenne journalière est ≥ 15°C [kWh] (idéalement pour des pas de temps de maximum 1h);
    try:
        dict_caracteristiques["EcartType_Quotidien_ete"] = pd_Alldata_id_e[["Jourlocal", col_electricity_use]].groupby("Jourlocal").std()[col_electricity_use].mean()
    except:
        dict_caracteristiques["EcartType_Quotidien_ete"] = None
    #_______________________________  
    #(19) L’écart-type journalier moyen de la consommation électrique durant les journées de mi-saison où la température moyenne journalière est entre 8 et 15°C [kWh] (idéalement pour des pas de temps de maximum 1h);
    try:
        dict_caracteristiques["EcartType_Quotidien_misaison"] = pd_Alldata_id_ms[["Jourlocal", col_electricity_use]].groupby("Jourlocal").std()[col_electricity_use].mean()
    except:
        dict_caracteristiques["EcartType_Quotidien_misaison"] = None
    #_______________________________  
    #(20) Le facteur d’utilisation en période hivernale où la température moyenne journalière est ≤ 8°C [%]. Le facteur d’utilisation est le rapport entre la consommation électrique moyenne d’un pas de temps et la consommation électrique maximale d’un pas de temps. Idéalement, le pas de temps est de maximum 1h.
    #Moyenne des FU quotidiens ?
    #calcul de l'écart-type par jour puis moyenne des valeurs (kWh/15min)
    tempo_dfFU = pd_Alldata_id_h[["Jourlocal", col_electricity_use]].groupby("Jourlocal").agg({col_electricity_use: ['mean', 'min', 'max']})
    
    try:
        tempo_dfFU["FU"] = tempo_dfFU[col_electricity_use]["mean"] / tempo_dfFU[col_electricity_use]["max"]
    except:
        tempo_dfFU["FU"] = None
    try:
        dict_caracteristiques["FU_Quotidien_hiver"] = tempo_dfFU["FU"].mean()
    except:
        dict_caracteristiques["FU_Quotidien_hiver"] = None
    #_______________________________  
    #(21) Le facteur d’utilisation en période estivale où la température moyenne journalière est ≥ 15°C [%];
    #calcul de l'écart-type par jour puis moyenne des valeurs (kWh/15min)
    tempo_dfFU = pd_Alldata_id_e[["Jourlocal", col_electricity_use]].groupby("Jourlocal").agg({col_electricity_use: ['mean', 'min', 'max']})
    try:
        tempo_dfFU["FU"] = tempo_dfFU[col_electricity_use]["mean"] / tempo_dfFU[col_electricity_use]["max"]
    except:
        tempo_dfFU["FU"] = None
    try:
        dict_caracteristiques["FU_Quotidien_ete"] = tempo_dfFU["FU"].mean()
    except:
        dict_caracteristiques["FU_Quotidien_ete"] = None
    #_______________________________  
    #(22) Le facteur d’utilisation durant la mi-saison où la température moyenne journalière est entre 8 et 15°C [%];
    #calcul de l'écart-type par jour puis moyenne des valeurs (kWh/15min)
    tempo_dfFU = pd_Alldata_id_ms[["Jourlocal", col_electricity_use]].groupby("Jourlocal").agg({col_electricity_use: ['mean', 'min', 'max']})
    try:
        tempo_dfFU["FU"] = tempo_dfFU[col_electricity_use]["mean"] / tempo_dfFU[col_electricity_use]["max"]
    except:
        tempo_dfFU["FU"] = None
    try:
        dict_caracteristiques["FU_Quotidien_misaison"] = tempo_dfFU["FU"].mean()
    except:
        dict_caracteristiques["FU_Quotidien_misaison"] = None
    #_______________________________  
    #(23) Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant les journées d’hiver où la température moyenne journalière est ≤ 8°C [-];

    #calcul des consommation de jour et nuit
    try:
        filter_23_J_d = (pd_Alldata_id_h["Heurelocal"] >=6) & (pd_Alldata_id_h["Heurelocal"] <=21)
        tempo_pd_Alldata_id_J = pd_Alldata_id_h[filter_23_J_d][["Jourlocal", col_electricity_use]].groupby("Jourlocal").mean()
        tempo_pd_Alldata_id_J = tempo_pd_Alldata_id_J.rename(columns={col_electricity_use: "energieactivelivree_kwh_J"})
        
        filter_23_N_d = (pd_Alldata_id_h["Heurelocal"] <=5) | (pd_Alldata_id_h["Heurelocal"] >=22)
        tempo_pd_Alldata_id_N = pd_Alldata_id_h[filter_23_N_d][["Jourlocal", col_electricity_use]].groupby("Jourlocal").mean()
        tempo_pd_Alldata_id_N = tempo_pd_Alldata_id_N.rename(columns={col_electricity_use: "energieactivelivree_kwh_N"})

        tempo_dfRatio = pd.merge(tempo_pd_Alldata_id_N, tempo_pd_Alldata_id_J, on="Jourlocal", how='inner')
        dict_caracteristiques["RatioJN_Quotidien_hiver"] = (tempo_dfRatio["energieactivelivree_kwh_J"]/tempo_dfRatio["energieactivelivree_kwh_N"]).mean()
    except:
        dict_caracteristiques["RatioJN_Quotidien_hiver"] = None
    #_______________________________  
    #(24) Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant les journées d’été où la température moyenne journalière est ≥ 15°C [-];
    #calcul des consommation de jour et nuit
    try:
        filter_23_J_d = (pd_Alldata_id_e["Heurelocal"] >=6) & (pd_Alldata_id_e["Heurelocal"] <=21)
        tempo_pd_Alldata_id_J = pd_Alldata_id_e[filter_23_J_d][["Jourlocal", col_electricity_use]].groupby("Jourlocal").mean()
        tempo_pd_Alldata_id_J = tempo_pd_Alldata_id_J.rename(columns={col_electricity_use: "energieactivelivree_kwh_J"})
        
        filter_23_N_d = (pd_Alldata_id_e["Heurelocal"] <=5) | (pd_Alldata_id_e["Heurelocal"] >=22)
        tempo_pd_Alldata_id_N = pd_Alldata_id_e[filter_23_N_d][["Jourlocal", col_electricity_use]].groupby("Jourlocal").mean()
        tempo_pd_Alldata_id_N = tempo_pd_Alldata_id_N.rename(columns={col_electricity_use: "energieactivelivree_kwh_N"})

        tempo_dfRatio = pd.merge(tempo_pd_Alldata_id_N, tempo_pd_Alldata_id_J, on="Jourlocal", how='inner')

        dict_caracteristiques["RatioJN_Quotidien_ete"] = (tempo_dfRatio["energieactivelivree_kwh_J"]/tempo_dfRatio["energieactivelivree_kwh_N"]).mean()
    except:
        dict_caracteristiques["RatioJN_Quotidien_ete"] = None
    #_______________________________
    #(25) Le ratio entre la consommation électrique moyenne de jour (6h à 22h) et de nuit durant la misaison où la température moyenne journalière est entre 8 et 15°C [-].
    #calcul des consommation de jour et nuit
    try:
        filter_23_J_d = (pd_Alldata_id_ms["Heurelocal"] >=6) & (pd_Alldata_id_ms["Heurelocal"] <=21)
        tempo_pd_Alldata_id_J = pd_Alldata_id_ms[filter_23_J_d][["Jourlocal", col_electricity_use]].groupby("Jourlocal").mean()
        tempo_pd_Alldata_id_J = tempo_pd_Alldata_id_J.rename(columns={col_electricity_use: "energieactivelivree_kwh_J"})
        
        filter_23_N_d = (pd_Alldata_id_ms["Heurelocal"] <=5) | (pd_Alldata_id_ms["Heurelocal"] >=22)
        tempo_pd_Alldata_id_N = pd_Alldata_id_ms[filter_23_N_d][["Jourlocal", col_electricity_use]].groupby("Jourlocal").mean()
        tempo_pd_Alldata_id_N = tempo_pd_Alldata_id_N.rename(columns={col_electricity_use: "energieactivelivree_kwh_N"})

        tempo_dfRatio = pd.merge(tempo_pd_Alldata_id_N, tempo_pd_Alldata_id_J, on="Jourlocal", how='inner')

        dict_caracteristiques["RatioJN_Quotidien_misaison"] = (tempo_dfRatio["energieactivelivree_kwh_J"]/tempo_dfRatio["energieactivelivree_kwh_N"]).mean()
    except:
        dict_caracteristiques["RatioJN_Quotidien_misaison"] = None

    return dict_caracteristiques
