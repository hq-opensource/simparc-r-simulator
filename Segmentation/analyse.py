import os
import sys
import yaml
from pathlib import Path
import polars as pl
import pyarrow.parquet as pq
import pandas as pd
import logging
from joblib import Parallel, delayed
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COLUMNS_TO_KEEP = ["segment_id", "building_id", "run_id", "seed", "isReference", 
        "Territoire_HQ", "Type_Batiment", "Superficie_Totale_cat", "An_ConstructionCode", "Source_Energie_Chauf",
        "An_Construction",
        "ChaufEau_ChaufType",
        "Chauffage_Logement",
        "Climatisation",
        "Cuisiniere_Energie",
        "Piscine_ChaufType",
        "Presence_Garage",
        "Presence_SousSol",
        "Radiant Barrier",
        "Region_Administrative",
        "Spa_Presence",
        "Superficie_Totale",
        "Type_Logement",
        "Vehicule_Presence",
        "heating_system_type",
        "pool_heater_type",
        "water_heater_fuel_type",
        "water_heater_type",
        "year_built",
        "End Use: Coal: Fireplace (MBtu)",
        "End Use: Coal: Heating (MBtu)",
        "End Use: Coal: Hot Water (MBtu)",
        "End Use: Coal: Mech Vent Preheating (MBtu)",
        "End Use: Electricity: Electric Vehicle Charging (MBtu)",
        "End Use: Electricity: Heating (MBtu)",
        "End Use: Electricity: Heating Fans/Pumps (MBtu)",
        "End Use: Electricity: Heating Heat Pump Backup (MBtu)",
        "End Use: Electricity: Heating Heat Pump Backup Fans/Pumps (MBtu)",
        "End Use: Electricity: Hot Water (MBtu)",
        "End Use: Electricity: Permanent Spa Heater (MBtu)",
        "End Use: Electricity: Pool Heater (MBtu)",
        "End Use: Fuel Oil: Fireplace (MBtu)",
        "End Use: Fuel Oil: Heating (MBtu)",
        "End Use: Fuel Oil: Heating Heat Pump Backup (MBtu)",
        "End Use: Fuel Oil: Hot Water (MBtu)",
        "End Use: Natural Gas: Fireplace (MBtu)",
        "End Use: Natural Gas: Heating (MBtu)",
        "End Use: Natural Gas: Heating Heat Pump Backup (MBtu)",
        "End Use: Natural Gas: Hot Water (MBtu)",
        "End Use: Propane: Fireplace (MBtu)",
        "End Use: Propane: Heating (MBtu)",
        "End Use: Propane: Heating Heat Pump Backup (MBtu)",
        "End Use: Propane: Hot Water (MBtu)",
        "End Use: Wood Cord: Fireplace (MBtu)",
        "End Use: Wood Cord: Heating (MBtu)",
        "End Use: Wood Cord: Heating Heat Pump Backup (MBtu)",
        "End Use: Wood Cord: Hot Water (MBtu)",
        "End Use: Wood Pellets: Fireplace (MBtu)",
        "End Use: Wood Pellets: Heating (MBtu)",
        "End Use: Wood Pellets: Heating Heat Pump Backup (MBtu)",
        "End Use: Wood Pellets: Hot Water (MBtu)",
        "Energy Use: Net (MBtu)",
        "Energy Use: Total (MBtu)",
        "Fuel Use: Coal: Total (MBtu)",
        "Fuel Use: Electricity: Net (MBtu)",
        "Fuel Use: Electricity: Total (MBtu)",
        "Fuel Use: Fuel Oil: Total (MBtu)",
        "Fuel Use: Natural Gas: Total (MBtu)",
        "Fuel Use: Propane: Total (MBtu)",
        "Fuel Use: Wood Cord: Total (MBtu)",
        "Fuel Use: Wood Pellets: Total (MBtu)",
        "Peak Electricity: Annual Net (W)",
        "Peak Electricity: Annual Total (W)",
        "Peak Electricity: Summer Net (W)",
        "Peak Electricity: Summer Total (W)",
        "Peak Electricity: Winter Net (W)",
        "Peak Electricity: Winter Total (W)",
        "Peak Load: Cooling: Delivered (kBtu/hr)",
        "Peak Load: Heating: Delivered (kBtu/hr)"
    ]



def combine_all_segments_data(base_results_path=None, n_jobs=-1, batch_size=10):
    """
    Combine JSON data from all buildings in all 225 segments using parallel processing.
    Filters columns directly at load time - only keeps COLUMNS_TO_KEEP columns.
    
    Args:
        base_results_path: Path to Segmentation/results directory
        n_jobs: Number of parallel jobs for building loading (-1 = all CPUs)
        batch_size: Number of segments per batch for memory management
        
    Returns:
        Filtered DataFrame with only COLUMNS_TO_KEEP columns
    """
    try:
        if base_results_path is None:
            base_results_path = Path(__file__).parent / "results"
        else:
            base_results_path = Path(base_results_path)
        
        logger.info("Starting to combine and filter JSON data from all 225 segments...")
        logger.info(f"Filtering to keep only {len(COLUMNS_TO_KEEP)} columns from COLUMNS_TO_KEEP")
        
        filtered_data = []  # Only store filtered data, never full data
        
        # Process all segments in parallel using multiprocessing
        segment_nums = list(range(1, 226))
        logger.info(f"Processing all 225 segments in parallel...")
        
        batch_results = Parallel(n_jobs=10, backend='multiprocessing')(
            delayed(_process_segment_filtered)(base_results_path, seg_num)
            for seg_num in tqdm(segment_nums, desc="Processing segments")
        )
        
        # Flatten results
        for segment_data_list in batch_results:
            if segment_data_list:
                filtered_data.extend(segment_data_list)
        
        if not filtered_data:
            logger.error("No data loaded from any segment")
            return None
        
        logger.info(f"Loaded and filtered data for {len(filtered_data)} buildings")
        
        # Create list of dictionaries for conversion to table
        logger.info("Creating filtered DataFrame...")
        # Use polars to create dataframe from list of dicts (faster)
        df_filtered = pl.DataFrame(filtered_data).to_pandas()
        
        # DEBUG: Check first few records before type conversion
        if len(df_filtered) > 0:
            logger.info(f"First record segment_id: {df_filtered.iloc[0].get('segment_id', 'MISSING')}, building_id: {df_filtered.iloc[0].get('building_id', 'MISSING')}")
        
        # Convert problematic types for numeric columns (excluding segment_id, building_id)
        #for col in df_filtered.columns:
        #    if col in ['segment_id', 'building_id']:
        #        # Keep as int, don't convert
        #        try:
        #            df_filtered[col] = df_filtered[col].astype('int64')
        #        except Exception as e:
        #            logger.warning(f"Failed to convert {col} to int64: {e}")
        #    elif df_filtered[col].dtype == 'object':
        #        try:
        #            df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce')
        #        except Exception as e:
        #            logger.debug(f"Could not convert column {col}: {e}")
        #            pass
        
        logger.info(f"Total records: {len(df_filtered)}")
        logger.info(f"Total columns: {len(df_filtered.columns)}")
        logger.info(f"Filtered columns: {sorted(df_filtered.columns.tolist())}")
        
        # DEBUG: Check segment_id after type conversion
        if len(df_filtered) > 0:
            logger.info(f"After conversion - First record segment_id: {df_filtered.iloc[0].get('segment_id', 'MISSING')}, building_id: {df_filtered.iloc[0].get('building_id', 'MISSING')}")
        
        return df_filtered
        
    except Exception as e:
        logger.error(f"Error combining segments JSON data: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


def _process_segment_filtered(base_results_path, segment_num):
    """Helper function to process a single segment with filtering at load time"""
    try:
        segment_name = f"Segment_{segment_num:03d}"
        segment_path = base_results_path / segment_name / "metadata.parquet"
        
        if not segment_path.exists():
            logger.warning(f"Segment path not found: {segment_path}")
            return None
        
        # Read parquet file using pyarrow
        table = pq.read_table(segment_path)
        
        # Get column names that exist in the file and are in COLUMNS_TO_KEEP
        existing_cols = table.column_names
        valid_cols = [col for col in COLUMNS_TO_KEEP if col in existing_cols]
        
        # If no valid columns found, return None
        if not valid_cols:
            logger.warning(f"No valid columns found in segment {segment_num}")
            return None
        
        # Select only the valid columns
        table = table.select(valid_cols)
        
        # Convert to list of dictionaries
        rows = table.to_pylist()
        
        # Add segment_id to each row
        for row in rows:
            row["segment_id"] = int(segment_num)
        
        return rows
        
    except Exception as e:
        logger.warning(f"Error processing segment {segment_num}: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return None

def main():
    """
    Main function for combining and filtering JSON data from all 225 segments.
   
    Returns:
        Filtered DataFrame with data from all 225 segments
    """

    try:
        logger.info("=" * 80)
        logger.info("COMBINING AND FILTERING JSON DATA FROM ALL 225 SEGMENTS")
        logger.info("=" * 80)
        df_filtered = combine_all_segments_data()

        if df_filtered is not None:
            #save the filtered DataFrame to a CSV file for future use
            filtered_csv_path = Path(__file__).parent / "results" / "filtered_combined_data.csv"
            df_filtered.to_csv(filtered_csv_path, index=False)
            
            logger.info("=" * 80)
            logger.info(f"✓ SUCCESS: Filtered DataFrame created and saved to CSV")
            logger.info(f"  File: {filtered_csv_path}")
            logger.info(f"  Total records: {len(df_filtered)}")
            logger.info(f"  Total columns: {len(df_filtered.columns)}")
            logger.info("=" * 80)
            return df_filtered
        else:
            logger.error("Failed to create filtered DataFrame")
            return None
    except Exception as e:
        logger.error(f"JSON data combination failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run: combines JSON data from all 225 segments and filters directly
    df_result = main()
    
    if df_result is not None:
        print(f"\nResult Summary:")
        print(f"  Rows: {len(df_result)}")
        print(f"  Columns: {len(df_result.columns)}")
        print(f"  DataFrame shape: {df_result.shape}")