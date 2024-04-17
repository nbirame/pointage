import pandas as pd


# Charger le fichier Excel dans un DataFrame
def reformatageFile():
    nom_fichier_excel = "D:\\extract Pointages\\pointage_Mois_fevrier.xlsx"
    # Remplacez 'nom_du_fichier.xlsx' par le nom de votre fichier Excel
    df = pd.read_excel(nom_fichier_excel)
    print(f"Colonnes: {df.columns}")
    header = ['Date\Time', 'First Name', 'COLvIDE', 'Last Name', 'User Policy', 'Employee ID', 'Morpho Device', 'Key',
              'Access']
    df.columns = header + list(df.columns[len(header):])
    print(f"Colonnes: {df.columns}")
    # Supprimer les 12 premières lignes
    df = df.iloc[14:]
    # df = df.dropna()
    df = df[~df.apply(lambda row: row.astype(str).str.contains('unknown user').any(), axis=1)]
    df = df.drop_duplicates()
    # Enregistrer le DataFrame modifié dans un nouveau fichier Excel
    nom_nouveau_fichier_excel = "D:\\extract Pointages\\pointage_Mois_fevrierReformat.xlsx"  # Nom du nouveau fichier Excel
    df.to_excel(nom_nouveau_fichier_excel, index=False)
