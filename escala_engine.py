from collections import deque
from datetime import datetime, timedelta
import json
import os
import random
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Any

class ScaleEngine:
    """
    Engine to manage team scale rotation, configuration persistence, and report generation.
    """
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to escala_config.json in the same folder as this script
            current_dir = Path(__file__).parent
            self.config_path = current_dir / "escala_config.json"
        else:
            self.config_path = Path(config_path)

        self.team: List[str] = []
        self.sectors: List[Dict[str, Any]] = []
        self.days_of_week = ["SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO"]
        self.load_config()

    def load_config(self) -> None:
        """
        Loads the team list and sector configurations from the JSON config file.
        If the file does not exist, it initializes empty lists.
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.team = data.get("team", [])
                    self.sectors = data.get("sectors", [])
            except Exception as e:
                print(f"Error loading configuration: {e}")
                self.team = []
                self.sectors = []
        else:
            self.team = []
            self.sectors = []

    def save_config(self, team: List[str], sectors: List[Dict[str, Any]]) -> None:
        """
        Saves the current team list and sector configurations to the JSON config file.
        """
        self.team = [name.strip().upper() for name in team if name.strip()]
        
        cleaned_sectors = []
        for sector in sectors:
            name = sector.get("name", "").strip().upper()
            capacity = int(sector.get("capacity", 1))
            if name:
                cleaned_sectors.append({"name": name, "capacity": capacity})
        
        self.sectors = cleaned_sectors

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"team": self.team, "sectors": self.sectors}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def generate_scale(self, week_number: int, max_consecutive_ptw_days: int = 1) -> List[Dict[str, str]]:
        """
        Generates the weekly scale based on rotation parameters.
        - Rotates the team by week number.
        - Isolates 'APOIO' as a weekly support role (gets the last person in the rotated queue).
        - For each day, copies the remaining queue, distributes roles, and rotates queue by -3.
        - Prevents the same person from being assigned to PTW on consecutive days
          (controlled by max_consecutive_ptw_days).

        :param week_number: The ISO week number to generate the scale for.
        :param max_consecutive_ptw_days: Maximum number of consecutive days a person can stay
            in PTW before being rotated out. Defaults to 1 (no back-to-back days).
        :return: A list of dicts, representing each day's allocation.
        """
        if not self.team:
            raise ValueError("A equipe está vazia. Adicione colaboradores antes de gerar a escala.")

        if not self.sectors:
            raise ValueError("Não há setores configurados. Adicione pelo menos um setor.")

        has_apoio = any(s["name"] == "APOIO" for s in self.sectors)
        ptw_sector = next((s for s in self.sectors if s["name"] == "PTW"), None)
        has_ptw = ptw_sector is not None

        base_team = deque(self.team)
        base_team.rotate(-(week_number - 1))

        weekly_apoio = None
        if has_apoio:
            if len(base_team) < 1:
                raise ValueError("Equipe insuficiente para selecionar um apoio semanal.")
            weekly_apoio = base_team.pop()

        scale_data: List[Dict[str, str]] = []
        recent_ptw_history: List[str] = []

        for day_index, day in enumerate(self.days_of_week):
            day_allocations = {"DIA": day.capitalize()}

            day_seed = (week_number * 100) + day_index
            random.seed(day_seed)

            shuffled_team_list = list(base_team)
            random.shuffle(shuffled_team_list)
            temp_team = deque(shuffled_team_list)

            for sector in self.sectors:
                sector_name = sector["name"]
                capacity = sector["capacity"]

                if sector_name == "APOIO":
                    continue

                if sector_name == "PTW" and has_ptw and max_consecutive_ptw_days >= 1:
                    ptw_candidates = list(temp_team)
                    selected_ptw = self._pick_ptw_candidate(
                        ptw_candidates, recent_ptw_history, max_consecutive_ptw_days
                    )
                    temp_team.remove(selected_ptw)
                    day_allocations[sector_name] = selected_ptw
                    recent_ptw_history.append(selected_ptw)
                    if len(recent_ptw_history) > max_consecutive_ptw_days:
                        recent_ptw_history.pop(0)
                    continue

                colaboradores = []
                for _ in range(capacity):
                    if temp_team:
                        colaboradores.append(temp_team.popleft())
                    else:
                        colaboradores.append("SEM COLABORADOR")

                day_allocations[sector_name] = ", ".join(colaboradores)

            if has_apoio:
                day_allocations["APOIO"] = weekly_apoio if weekly_apoio else "SEM COLABORADOR"

            scale_data.append(day_allocations)
            base_team.rotate(-3)

        return scale_data

    def _pick_ptw_candidate(
        self,
        candidates: List[str],
        recent_ptw_history: List[str],
        max_consecutive_ptw_days: int,
    ) -> str:
        """
        Selects a PTW candidate avoiding people who have been in PTW
        for the last `max_consecutive_ptw_days` consecutive days.
        Falls back to the first candidate if no eligible person is found.

        :param candidates: Ordered list of available team members for this day.
        :param recent_ptw_history: List of names who were in PTW in recent days (oldest first).
        :param max_consecutive_ptw_days: How many recent days to check for back-to-back assignment.
        :return: The name of the selected PTW collaborator.
        """
        blocked = set(recent_ptw_history[-max_consecutive_ptw_days:])
        for candidate in candidates:
            if candidate not in blocked:
                return candidate
        return candidates[0]

    def export_to_excel(self, scale_data: List[Dict[str, str]], week_number: int, output_dir: str = None) -> str:
        """
        Exports the generated scale data to an Excel file and returns the file path.
        
        :param scale_data: The scale data generated by generate_scale().
        :param week_number: The week number.
        :param output_dir: The directory to save the Excel file. Defaults to user's Downloads.
        :return: Path to the generated Excel file.
        """
        if output_dir is None:
            home = Path.home()
            output_dir = str(home / "Downloads")
            
        filename = f"escala_semana_{week_number}.xlsx"
        full_path = os.path.join(output_dir, filename)
        
        # Date details for sheet header
        current_year = datetime.now().year
        start_date = datetime.fromisocalendar(current_year, week_number, 1)
        end_date = start_date + timedelta(days=5)
        
        sheet_name = f"ESCALA {start_date.strftime('%d-%m')} A {end_date.strftime('%d-%m')}"
        
        df = pd.DataFrame(scale_data)
        
        # Ensure the directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        df.to_excel(full_path, index=False, sheet_name=sheet_name)
        return full_path
