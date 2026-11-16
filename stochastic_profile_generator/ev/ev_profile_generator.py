import numpy as np
import pandas as pd

"""
Module that creates EV level 2 residential charging profiles. 

The algorithm (contained in function charge_profiles below) was used as a basis for paper 
"Energy-Based Probabilistic Model of Residential Electric Vehicle Load". It is a modified 
version of the algorithm used in the project SCENARIO.

The algorithm was created by Samuel Aubert, Contrôle et gestion de réseaux, IREQ.
August 2024

Permission of the author (S. Aubert) is required for any use of this code.
"""


def charge_profiles(jt, power, delta=4, epsilon=0.79, alpha1=8.0, alpha2=3.0, max_charge_events=2, rng=np.random.default_rng()):
    """
    Creation of the charging profiles.

    :param jt: Tuple composed of the type of day J (0: weekday, 1: weekend / holiday) and period of the year T
        (0: November - March, 1: April - October)
    :param power: Array containing the nominal charging power values of all electric vehicles
    :param delta: Integer (multiple of 15 min) giving the minimum dead time between charging events,
        e.g. '1' implies that any two charging events are separated by at least 15 min.
    :param epsilon: Fraction of the nominal power that is observed on average during charging
    :param alpha1: Parameter that modifies the negative threshold of acceptable energy discrepancy
    :param alpha2: Parameter that modifies the positive threshold of acceptable energy discrepancy
    :return:    0: Structure of the charging profile ('1' if charge active, '0' otherwise)
                1: Charging profile with power values
                2: Number of charge events per ev client
                3: Cumulative daily energy for every EV client (array)
                4: Cumulative target daily energy for every EV client (array)
                5: Total number of times that a profile cannot be completed
    """
    e_densities_all = np.load(r"stochastic_profile_generator/ev/energy_density_2209-2308.npy",
                              allow_pickle=True)
    c_densities_all = np.load(r"stochastic_profile_generator/ev/charge_density_2209-2308.npy",
                              allow_pickle=True)

    # Include profiles of low energy (lower than alpha2 * e_base)
    # Each profile = one charging instance of duration less than or equal to alpha2
    c_densities_short_duration_all = (c_densities_all[:, :int(alpha2) * 96] /
                                      np.transpose([np.sum(c_densities_all[:, :int(alpha2) * 96], axis=1)]))

    distribution_indices = np.array([1, 1]) * (jt[0]*4 + jt[1]*2) + np.array([0, 1])
    # Binomial number, e.g. (JTP) = (011) implies 0*2^2 + 1*2 + 1*2^0 = 3

    # Selection of the energy and charge distributions for the specified day type (J) and period (T)
    # Both power categories are kept (index 0: low power; index 1: high power).
    e_densities = e_densities_all[distribution_indices, :]
    c_densities = c_densities_all[distribution_indices, :]

    # Include the profiles of low energy
    c_densities_short_duration = c_densities_short_duration_all[distribution_indices, :]

    n_ev_clients = len(power)
    profiles = np.zeros((n_ev_clients, 96))
    e_base = epsilon * power * 0.25   # kWh (determine when sufficient charging events have been generated)
    e_tot = np.zeros(n_ev_clients)      # Cumulative daily energy for every EV client
    e_day_all = np.zeros(n_ev_clients)  # Cumulative target daily energy for every EV client
    n_chrg = np.zeros(n_ev_clients, dtype=int)     # Number of charge events per ev client

    client_indices = np.arange(n_ev_clients)
    index_sets = [client_indices[power <= 3.7], client_indices[power > 3.7]]

    limit_trials = 200  # Maximum allowed number of trials to build profiles in one power category
    incomplete_p = 0    # Track the number of profiles that cannot be completed

    #rng = np.random.default_rng()    # Add a seed argument in due time, e.g. default_rng(seed=41)

    for z in range(len(index_sets)):
        ind_pwr = index_sets[z]
        e_b = e_base[ind_pwr]     # Base units of energy in the current power category

        # Sampled daily energy targets
        e_day = rng.choice(e_densities.shape[1], size=ind_pwr.size, p=e_densities[z])

        e_day_all[ind_pwr] = e_day
        e_day = e_day.astype(float)
        e_r = e_day.copy()  # Residual energy

        count = 0   # Number of takes to build all profiles in the power category in process

        # Include the profiles of low energy
        if np.any(np.logical_and(e_day > 0, e_day <= alpha2 * e_b)):
            ind_low_energy = ind_pwr[np.logical_and(e_day > 0, e_day <= alpha2 * e_b)]
            n_el_low_energy = ind_low_energy.size
            rdm_ind_low_energy = rng.choice(c_densities_short_duration.shape[1], size=n_el_low_energy,
                                            p=c_densities_short_duration[z])
            ts = rdm_ind_low_energy % 96
            dur = rdm_ind_low_energy // 96 + 1
            i_le = np.repeat(ind_low_energy, dur)
            j_le = (np.repeat(ts, dur) + np.concatenate([np.arange(d) for d in dur])) % 96
            profiles[i_le, j_le] = 1

        while np.any(np.logical_and(e_day > 0, e_r > alpha2 * e_b)):
            incomplete_bool = np.logical_and(e_day > 0, e_r > alpha2 * e_b)
            incomplete_ind = ind_pwr[incomplete_bool]
            n_el = incomplete_ind.size  # Number of elements for which profiles are to be created

            rdm_ind = rng.choice(c_densities.shape[1], size=n_el, p=c_densities[z])
            ts = rdm_ind % 96
            dur = rdm_ind // 96 + 1

            # Charge events + buffer (delta factor)
            ts_b = (ts - delta + 96) % 96   # '% 96' to take into consideration cyclic day
            dur_b = dur + 2 * delta

            i1 = np.repeat(incomplete_ind, dur)
            j1 = (np.repeat(ts, dur) + np.concatenate([np.arange(d) for d in dur])) % 96

            ib = np.repeat(incomplete_ind, dur_b)
            jb = (np.repeat(ts_b, dur_b) + np.concatenate([np.arange(d) for d in dur_b])) % 96

            conflict_rows = ib[profiles[ib, jb] > 0]
            j1 = j1[np.isin(i1, conflict_rows, invert=True)]
            i1 = i1[np.isin(i1, conflict_rows, invert=True)]
            i1_nonrepeated = np.unique(i1)  # Indices of non-conflicting rows (clients)

            # Boolean indicators of *** no conflict elements ***
            indicator1 = np.isin(incomplete_ind, i1_nonrepeated)        # Indication w.r.t. profile elements
            indicator2 = np.isin(ind_pwr, i1_nonrepeated)   # Indication w.r.t. all elements in power category

            e_i = np.zeros_like(ind_pwr, dtype=float)   # Energy increments (kWh)
            e_i[indicator2] = epsilon * power[incomplete_ind[indicator1]] * dur[indicator1] * 0.25

            e_rcheck = e_r - e_i
            # Additionally accept elements with *** properly sized incremental energy ***
            accept_condition = np.logical_and(indicator2, np.greater_equal(e_rcheck, -alpha1 * e_b))
            e_r[accept_condition] = e_rcheck[accept_condition]

            i2 = ind_pwr[accept_condition]
            i3 = i1[np.isin(i1, i2)]
            j3 = j1[np.isin(i1, i2)]

            profiles[i3, j3] = 1
            n_chrg[i2] += 1
            e_tot[i2] += e_i[accept_condition]

            # Limit the number of charge events
            if np.any(n_chrg[i2] > max_charge_events):
                i4 = i2[n_chrg[i2] > max_charge_events]     # Condition on the maximum number of charge events

                e_r[np.isin(ind_pwr, i4)] = e_day[np.isin(ind_pwr, i4)]
                profiles[i4, :] = 0
                n_chrg[i4] = 0
                e_tot[i4] = 0

            count += 1
            if count == limit_trials:
                incomplete_p += len(incomplete_ind)
                break

    profiles_pwr = profiles * np.array([power * epsilon]).T

    #return profiles, profiles_pwr, n_chrg, e_tot, e_day_all, incomplete_p
    return profiles_pwr

def generateSingleAnnuelVEHourlyProfile(EV_Type, year, rng):
    """
    Generate a single annual EV charging hourly profile for given power ratings and year.

    Parameters:
    year (int): Year for which the profile is generated.
    EV_Type (str): Type of the electric vehicle (e.g., 'Hybrid', 'Battery Electric').
    

    Returns:
    np.array: Hourly EV charging profile for the year (1 january to 31 december).
    """

    # Estimer la puissance de recharge en kW selon le type de VE
    if EV_Type == 'Hybrid':
        li_power = [3.3, 3.6, 3.7]              # Charging power of each type of EV (kW)
        li_share = [0.07, 0.06, 0.03]       # Share of each EV type in the vehicle fleet
        ar_share = np.array(li_share) / np.sum(li_share)
    else:
        li_power = [6.6, 7.2]              # Charging power of each type of EV (kW)
        li_share = [0.3, 0.54]       # Share of each EV type in the vehicle fleet
        ar_share = np.array(li_share) / np.sum(li_share)
    power = rng.choice(li_power, size=1, p=ar_share)[0]

    # Definir les types de jours et périodes de l'année
    liDayType = [0,1] # 0: Weekday, 1: Weekend/Holiday
    liPeriodOfYear = [0,1]  # 0: Sept-March, 1: April-August
    liTJ = [(j, t) for j in liDayType for t in liPeriodOfYear]
        
    # Create a DataFrame for the year with day types and periods
    idxDay = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31 23:00', freq='D')
    dfDaily = pd.DataFrame(index=idxDay)
    dfDaily['DayType'] = np.where(dfDaily.index.dayofweek < 5, 0, 1)  # 0: Weekday, 1: Weekend
    dfDaily['PeriodOfYear'] = np.where((dfDaily.index.month >= 4) & (dfDaily.index.month <= 8), 1, 0)  # 0: Sept-March, 1: April-August
    dfDaily['JT'] = list(zip(dfDaily['DayType'], dfDaily['PeriodOfYear']))

    # Pour chaque type de jour et période
    for tuJT in liTJ :

        # Générer un vecteur de puissance ayant nbProfileDifferent profils différents
        nbProfileDifferent = 10
        ev_power_expanded = np.repeat([power], nbProfileDifferent)

        # Génerer nbProfileDifferent profils associé à la puissance donnée
        ar_profile_15min = charge_profiles(tuJT, ev_power_expanded, rng=rng)
        
        # Convertir dles 96 valeurs (15 min) à 24 valeurs (1 heure) en moyennant
        ar_profile_1h_x = np.array([np.mean(np.split(row, 24), axis=1) for row in ar_profile_15min])
       
        # Sélectionner aléatoirement des profils pour chaque jour du type tuJT
        nbTuIJ = dfDaily['JT'].value_counts()[tuJT]
        ar_profile_1h = [ar_profile_1h_x[rng.integers(0, nbProfileDifferent)] for i in range(nbTuIJ)]

        # Affecter les profils générés aux jours correspondants dans le DataFrame annuel
        mask = dfDaily['JT'] == tuJT
        dfDaily.loc[mask, range(24)] = ar_profile_1h

    ar_AnnualProfile = dfDaily[range(24)].stack().values
    


    return ar_AnnualProfile



if __name__ == "__main__":
    year = 2022
    VE_Type = 'Hybrid'

    ar = generateSingleAnnuelVEHourlyProfile(VE_Type, year, np.random.default_rng())