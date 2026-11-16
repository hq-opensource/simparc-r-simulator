from postprocess.Analyse import _end_use_focus_kpis


def test_end_use_focus_profiles_include_missing_day_type_variants():
    entries = _end_use_focus_kpis("End Use Electricity Electric Vehicles", pas_de_temps="1h")
    profile_params = [
        entry["params"]
        for entry in entries
        if entry["name"] == "Profil"
    ]

    expected = {
        ("Annee", "Semaine"),
        ("Annee", "FinDeSemaine"),
        ("Annee", "Tous"),
        ("Hiver", "Semaine"),
        ("Hiver", "FinDeSemaine"),
        ("Hiver", "Tous"),
        ("Ete", "Semaine"),
        ("Ete", "FinDeSemaine"),
        ("Ete", "Tous"),
        ("Automne", "Semaine"),
        ("Automne", "FinDeSemaine"),
        ("Automne", "Tous"),
        ("Printemps", "Semaine"),
        ("Printemps", "FinDeSemaine"),
        ("Printemps", "Tous"),
        ("Janvier", "JourPreconfigure"),
    }

    found = {
        (params["periode"], params["type_jour"])
        for params in profile_params
    }

    missing = expected - found
    assert not missing, f"Missing profile KPI combinations: {sorted(missing)}"
