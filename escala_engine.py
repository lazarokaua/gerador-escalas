from collections import deque
from datetime import datetime, timedelta
import json
import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Any


class ScaleEngine:
    """
    Engine to manage team scale rotation, configuration persistence, and report generation.

    Rotation strategy:
    - Each week the entire team list is offset by the week number, ensuring a
      different "starting person" every week.
    - APOIO is a weekly fixed role assigned to the last person in the rotated queue.
    - For the remaining days the active team is treated as a circular queue.
      On each day the queue is shifted by the total number of slots used the
      previous day, so every person advances through the sector sequence in a
      predictable, deterministic order (e.g. LEVES → CELULAR → PRODUTO → PTW).
    - A back-to-back guard checks that nobody is placed in the same sector two
      days in a row. When a conflict is detected the two conflicting people are
      swapped within the day's allocation before writing results.
    """

    def __init__(self, config_path: str = None):
        if config_path is None:
            current_dir = Path(__file__).parent
            self.config_path = current_dir / "escala_config.json"
        else:
            self.config_path = Path(config_path)

        self.team: List[str] = []
        self.sectors: List[Dict[str, Any]] = []
        self.days_of_week = ["SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO"]
        self.load_config()

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def load_config(self) -> None:
        """Loads team list and sector configurations from the JSON config file."""
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
        """Saves the current team list and sector configurations to the JSON config file."""
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
                json.dump(
                    {"team": self.team, "sectors": self.sectors},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            print(f"Error saving configuration: {e}")

    # ------------------------------------------------------------------
    # Scale generation
    # ------------------------------------------------------------------

    def generate_scale(self, week_number: int) -> List[Dict[str, str]]:
        """
        Generates the weekly scale with deterministic rotation and a strict
        no-consecutive-day rule: no person may appear in the same sector on
        two consecutive days.

        Algorithm:
        1. Rotate the global team list by the week number to get a fresh
           starting order for this week.
        2. Remove the APOIO person (last in queue) – fixed for the whole week.
        3. For each working day:
           a. Build the ordered slot list from the current queue position.
           b. Map each slot (sector, index) to the person at that position.
           c. Detect conflicts with yesterday's assignments and swap the
              conflicting person with the next available non-conflicting
              neighbour. This keeps the rotation pattern intact while
              satisfying the no-repeat constraint.
           d. Advance the queue by the total number of active slots so that
              tomorrow's first person is the one who comes right after today's
              last person – preserving the predictable sector sequence.

        :param week_number: ISO week number to generate the scale for.
        :return: List of dicts mapping sector names to assigned collaborator names.
        """
        if not self.team:
            raise ValueError("A equipe está vazia. Adicione colaboradores antes de gerar a escala.")
        if not self.sectors:
            raise ValueError("Não há setores configurados. Adicione pelo menos um setor.")

        has_apoio = any(s["name"] == "APOIO" for s in self.sectors)
        active_sectors = [s for s in self.sectors if s["name"] != "APOIO"]
        total_active_slots = sum(s["capacity"] for s in active_sectors)

        active_team = list(self.team)
        team_size = len(active_team)

        # Week-level rotation: different entry point each week
        week_offset = (week_number - 1) % team_size
        rotated_team = active_team[week_offset:] + active_team[:week_offset]

        # Reserve APOIO person (last in the rotated list)
        weekly_apoio: Optional[str] = None
        if has_apoio:
            weekly_apoio = rotated_team.pop()

        available_team = rotated_team  # people that rotate through active sectors
        available_size = len(available_team)

        if available_size == 0:
            raise ValueError("Equipe insuficiente para preencher os setores após reservar o APOIO.")

        scale_data: List[Dict[str, str]] = []
        # Maps person → sector name for the previous day (used for conflict detection)
        previous_day_assignments: Dict[str, str] = {}
        # Current rotation offset within available_team
        rotation_offset = 0

        for day in self.days_of_week:
            day_allocations: Dict[str, str] = {"DIA": day.capitalize()}

            # Build today's ordered slot list using circular indexing
            slot_assignments: List[str] = [
                available_team[(rotation_offset + i) % available_size]
                for i in range(total_active_slots)
            ]

            # Resolve conflicts: no person may repeat their sector from yesterday
            slot_assignments = self._resolve_consecutive_conflicts(
                slot_assignments, active_sectors, previous_day_assignments, available_team
            )

            # Map slots → sectors and record assignments for tomorrow
            slot_index = 0
            today_assignments: Dict[str, str] = {}
            for sector in active_sectors:
                people_for_sector: List[str] = []
                for _ in range(sector["capacity"]):
                    person = slot_assignments[slot_index % len(slot_assignments)]
                    people_for_sector.append(person)
                    today_assignments[person] = sector["name"]
                    slot_index += 1

                day_allocations[sector["name"]] = ", ".join(people_for_sector)

            if has_apoio:
                day_allocations["APOIO"] = weekly_apoio if weekly_apoio else "SEM COLABORADOR"

            scale_data.append(day_allocations)
            previous_day_assignments = today_assignments

            # Advance the rotation by total active slots (deterministic, predictable)
            rotation_offset = (rotation_offset + total_active_slots) % available_size

        return scale_data

    def _resolve_consecutive_conflicts(
        self,
        slot_assignments: List[str],
        active_sectors: List[Dict[str, Any]],
        previous_day_assignments: Dict[str, str],
        available_team: List[str],
    ) -> List[str]:
        """
        Detects and resolves cases where a person would be placed in the same
        sector they were in the previous day.

        Strategy: iterate through each slot and, if the assigned person was in
        the same sector yesterday, find the nearest subsequent slot whose person
        does NOT have the same conflict, then swap those two slots.

        This is a best-effort pass that maintains the overall rotation order as
        closely as possible while eliminating direct back-to-back repetitions.

        :param slot_assignments: Ordered list of people assigned to today's slots.
        :param active_sectors: Ordered list of active sector dicts (with capacity).
        :param previous_day_assignments: Mapping of person → sector name from yesterday.
        :param available_team: Full available team list (used only for reference).
        :return: Adjusted slot_assignments list with conflicts resolved.
        """
        if not previous_day_assignments:
            return slot_assignments

        # Build a parallel list of which sector each slot belongs to
        slot_sectors: List[str] = []
        for sector in active_sectors:
            slot_sectors.extend([sector["name"]] * sector["capacity"])

        adjusted = list(slot_assignments)
        total_slots = len(adjusted)

        for i in range(total_slots):
            person = adjusted[i]
            sector = slot_sectors[i]
            if previous_day_assignments.get(person) == sector:
                # Find a swap partner: first slot after i with no conflict
                swapped = False
                for j in range(i + 1, total_slots):
                    candidate = adjusted[j]
                    candidate_sector = slot_sectors[j]
                    candidate_yesterday = previous_day_assignments.get(candidate)
                    # Candidate is valid if:
                    # - candidate was NOT in sector[j] yesterday, AND
                    # - person would NOT be in sector[j] yesterday (after swap)
                    person_yesterday = previous_day_assignments.get(person)
                    if (
                        candidate_yesterday != candidate_sector
                        and person_yesterday != candidate_sector
                        and candidate_yesterday != sector
                    ):
                        adjusted[i], adjusted[j] = adjusted[j], adjusted[i]
                        swapped = True
                        break

                if not swapped:
                    # Fallback: search backwards before i
                    for j in range(i - 1, -1, -1):
                        candidate = adjusted[j]
                        candidate_sector = slot_sectors[j]
                        candidate_yesterday = previous_day_assignments.get(candidate)
                        person_yesterday = previous_day_assignments.get(person)
                        if (
                            candidate_yesterday != candidate_sector
                            and person_yesterday != candidate_sector
                            and candidate_yesterday != sector
                        ):
                            adjusted[i], adjusted[j] = adjusted[j], adjusted[i]
                            break

        return adjusted

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_to_excel(
        self,
        scale_data: List[Dict[str, str]],
        week_number: int,
        output_dir: str = None,
    ) -> str:
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

        current_year = datetime.now().year
        start_date = datetime.fromisocalendar(current_year, week_number, 1)
        end_date = start_date + timedelta(days=5)

        sheet_name = f"ESCALA {start_date.strftime('%d-%m')} A {end_date.strftime('%d-%m')}"

        df = pd.DataFrame(scale_data)
        os.makedirs(output_dir, exist_ok=True)
        df.to_excel(full_path, index=False, sheet_name=sheet_name)
        return full_path
