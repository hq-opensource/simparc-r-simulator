import os
import shutil
from pathlib import Path
from datetime import datetime
import sys
# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

project_yml = True
segments = True
config = True
metadata = True
filtered_combined_data = True
sampling_analysis = True


import os
import shutil
from datetime import datetime

import os
import shutil
from datetime import datetime

import os
import shutil
from datetime import datetime

def backup_files(source_folder, destination_folder, 
                 allowed_folders=None,
                 allowed_extensions=None, 
                 allowed_filenames=None, 
                 exclude_folders=None,
                 case_sensitive=False,
                 use_timestamp=False):
    """
    Fonction universelle adaptée pour filtrer les dossiers (comme metadata.parquet) 
    à n'importe quel niveau de l'arborescence.
    """
    if not os.path.exists(source_folder):
        print(f"Erreur : La source '{source_folder}' n'existe pas.")
        return

    if os.path.isfile(source_folder):
        filename = os.path.basename(source_folder)
        source_folder = os.path.dirname(source_folder)
        allowed_filenames = [filename]

    if allowed_extensions and not case_sensitive:
        allowed_extensions = [ext.lower() for ext in allowed_extensions]
    if allowed_filenames and not case_sensitive:
        allowed_filenames = [name.lower() for name in allowed_filenames]
    if allowed_folders and not case_sensitive:
        allowed_folders = [folder.lower() for folder in allowed_folders]
    
    if exclude_folders is None:
        exclude_folders = []
    
    dest_dir_name = os.path.basename(os.path.normpath(destination_folder))
    if dest_dir_name and dest_dir_name not in exclude_folders:
        exclude_folders.append(dest_dir_name)

    if not case_sensitive:
        exclude_folders = [folder.lower() for folder in exclude_folders]

    if use_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_target_dir = os.path.join(destination_folder, f"backup_general_{timestamp}")
    else:
        backup_target_dir = destination_folder

    os.makedirs(backup_target_dir, exist_ok=True)
    files_copied = 0

    for root, dirs, files in os.walk(source_folder, topdown=True):
        # 1. Gestion des EXCLUSIONS
        if not case_sensitive:
            dirs[:] = [d for d in dirs if d.lower() not in exclude_folders]
        else:
            dirs[:] = [d for d in dirs if d not in exclude_folders]

        # 2. FILTRE FLUIDE DES DOSSIERS AUTORISÉS (allowed_folders)
        # On vérifie si on est déjà INSIDE un dossier autorisé ou si on doit filtrer
        if allowed_folders:
            # Calculer le chemin relatif pour savoir si on est dans un sous-dossier autorisé
            rel_path_parts = os.path.relpath(root, source_folder).replace("\\", "/").lower().split("/")
            inside_allowed = any(allowed in rel_path_parts for allowed in allowed_folders)
            
            # Si on n'est pas encore dans un dossier autorisé, on filtre les 'dirs' disponibles
            if not inside_allowed:
                if not case_sensitive:
                    # Garde le dossier s'il est dans la liste OU s'il peut mener à un dossier autorisé
                    dirs[:] = [d for d in dirs if d.lower() in allowed_folders or any(allowed in d.lower() for allowed in allowed_folders) or d.lower().startswith("segment_")]
                else:
                    dirs[:] = [d for d in dirs if d in allowed_folders or d.startswith("Segment_")]
                
                # On ignore les fichiers en dehors des dossiers autorisés
                if not allowed_filenames:
                    files = []

        # Copie des fichiers qualifiés
        for filename in files:
            name_to_check = filename if case_sensitive else filename.lower()
            _, ext = os.path.splitext(name_to_check)

            if allowed_extensions and ext not in allowed_extensions:
                continue
            if allowed_filenames and name_to_check not in allowed_filenames:
                continue

            source_file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(root, source_folder)
            
            target_sub_dir = os.path.join(backup_target_dir, relative_path) if relative_path != "." else backup_target_dir
            os.makedirs(target_sub_dir, exist_ok=True)
            
            shutil.copy2(source_file_path, target_sub_dir)
            print(f"Copié : {os.path.join(relative_path, filename)}")
            files_copied += 1

    print(f"\nSauvegarde terminée. Total : {files_copied} fichier(s) copié(s) dans {backup_target_dir}")



def main():
    # Exemple d'utilisation
    #copy file and folder to backup
    use_timestamp = False
    date_time_now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_folder = os.path.join(project_root, "backup_results")
    dest_folder = os.path.join(backup_folder, date_time_now)

    if project_yml:
        SRC = os.path.join(project_root)
        DEST = os.path.join(dest_folder)
        backup_files(
            source_folder=SRC, 
            destination_folder=DEST,
            allowed_filenames=["project.yaml"],
            exclude_folders=["backup_results"],
            #allowed_extensions=[".json", ".txt"], 
            use_timestamp=use_timestamp
        )
    
    if segments:
        SRC = os.path.join(project_root, "segments")
        DEST = os.path.join(dest_folder, "segments")
        backup_files(
            source_folder=SRC, 
            destination_folder=DEST, 
            #allowed_extensions=[".json", ".txt"], 
            exclude_folders=["backup_results"],
            use_timestamp=use_timestamp
        )

    if config:
        SRC = os.path.join(project_root, "config")
        DEST = os.path.join(dest_folder, "config")
        backup_files(
            source_folder=SRC, 
            destination_folder=DEST, 
            exclude_folders=["backup_results"],
            #allowed_extensions=[".json", ".txt"], 
            use_timestamp=use_timestamp
        )
    
    if metadata:
        SRC = os.path.join(project_root, "results")
        DEST = os.path.join(dest_folder, "results")
        backup_files(
            source_folder=SRC, 
            destination_folder=DEST, 
            exclude_folders=["backup_results"],
            allowed_folders=["metadata.parquet"], 
            use_timestamp=use_timestamp
        )
    
    if filtered_combined_data:
        SRC = os.path.join(project_root, "results")
        DEST = os.path.join(dest_folder, "results")
        backup_files(
            source_folder=SRC, 
            destination_folder=DEST, 
            exclude_folders=["backup_results"],
            allowed_filenames=["filtered_combined_data.csv"], 
            use_timestamp=use_timestamp
        )
    
    if sampling_analysis:
        SRC = os.path.join(project_root)
        DEST = os.path.join(dest_folder)
        backup_files(
            source_folder=SRC, 
            destination_folder=DEST, 
            exclude_folders=["backup_results"],
            allowed_filenames=["df_all.csv", "df_segment_counts.csv","df_segment_proportions.csv"], 
            use_timestamp=use_timestamp
        )

if __name__ == "__main__":
    main()