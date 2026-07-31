import csv
import os
from typing import List, Dict, Optional, Any

class RobustCSVWriterTool:
    def __init__(self):
        self.name = "Robust CSV Writer"
        self.description = (
            "Advanced CSV writer with data cleaning, validation, and flexible formatting. "
            "Handles inconsistent data structures, missing values, and provides detailed feedback."
        )

    def _run(
        self, 
        data: List[Dict], 
        filename: str = "data.csv",
        append: bool = False,
        delimiter: str = ',',
        clean_data: bool = True,
        fieldnames: List[str] = None
    ) -> str:
        try:
            # Validate inputs
            if not data:
                return "Error: No data provided."
            
            if not isinstance(data, list):
                return f"Error: Expected list, got {type(data).__name__}"
            
            # Ensure .csv extension
            if not filename.endswith('.csv'):
                filename += '.csv'
            
            # Create directory if needed
            directory = os.path.dirname(filename)
            if directory:
                os.makedirs(directory, exist_ok=True)
            
            # Clean and normalize data if requested
            if clean_data:
                data = self._clean_data(data)
            
            # Extract all unique headers if not provided
            if not fieldnames:
                all_headers = set()
                for row in data:
                    if isinstance(row, dict):
                        all_headers.update(row.keys())
                
                headers = sorted(all_headers)
            else:
                headers = fieldnames
            
            if not headers:
                return "Error: No valid headers found in data."
            
            # Determine mode
            mode = 'a' if append else 'w'
            file_exists = os.path.exists(filename)
            
            # Write CSV
            with open(filename, mode=mode, newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=headers,
                    delimiter=delimiter,
                    extrasaction='ignore',
                    restval='N/A'
                )
                
                if not append or not file_exists:
                    writer.writeheader()
                
                # Write only dictionary rows
                valid_rows = [row for row in data if isinstance(row, dict)]
                writer.writerows(valid_rows)
            
            return (f"Success: {len(valid_rows)} rows written to '{filename}' "
                   f"with {len(headers)} columns")
            
        except Exception as e:
            return f"Error: {type(e).__name__} - {str(e)}"
    
    def _clean_data(self, data: List[Dict]) -> List[Dict]:
        """Clean and normalize data"""
        cleaned = []
        for row in data:
            if not isinstance(row, dict):
                continue
            
            cleaned_row = {}
            for key, value in row.items():
                # Convert keys to strings and clean them
                clean_key = str(key).strip()
                
                # Handle various value types
                if value is None:
                    cleaned_row[clean_key] = ''
                elif isinstance(value, (list, dict)):
                    cleaned_row[clean_key] = str(value)
                else:
                    cleaned_row[clean_key] = str(value).strip()
            
            cleaned.append(cleaned_row)
        
        return cleaned