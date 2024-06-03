import streamlit as st
import pandas as pd
import requests
from math import ceil
from ortools.linear_solver import pywraplp

# Load CSV files
def load_data(materials_csv, types_csv):
    materials = pd.read_csv(materials_csv)
    types = pd.read_csv(types_csv)

    # Create dictionary for ore data
    ore_data = {}
    for _, row in materials.iterrows():
        ore_id = row['typeID']
        if ore_id not in ore_data:
            ore_data[ore_id] = {'minerals': {}}
        ore_data[ore_id]['minerals'][row['materialTypeID']] = row['quantity']

    for ore_id in ore_data:
        ore_info = types[types['typeID'] == ore_id].iloc[0]
        ore_data[ore_id]['name'] = ore_info['typeName']
        ore_data[ore_id]['volume'] = ore_info['volume']

    return ore_data

def get_market_data(type_ids, station_id=60003760):
    base_url = "https://market.fuzzwork.co.uk/aggregates/"
    params = {"station": station_id, "types": ",".join(map(str, type_ids))}
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    return response.json()

def optimize_ores(ore_data, market_data, mineral_requirements, efficiency=0.739):
    # Initialize the solver
    solver = pywraplp.Solver.CreateSolver('GLOP')
    if not solver:
        st.error("Solver not created.")
        return None

    # Define variables for the amount of each type of ore to buy in batches of 100
    ore_vars = {}
    for ore_id, data in ore_data.items():
        ore_vars[ore_id] = solver.IntVar(0, solver.infinity(), data['name'])

    # Define the objective function (minimize cost)
    objective = solver.Objective()
    for ore_id, data in ore_data.items():
        if str(ore_id) in market_data and 'sell' in market_data[str(ore_id)] and 'weightedAverage' in market_data[str(ore_id)]['sell']:
            price = float(market_data[str(ore_id)]['sell']['weightedAverage'])
            objective.SetCoefficient(ore_vars[ore_id], price)

    objective.SetMinimization()

    # Define the constraints for mineral requirements
    constraints = {}
    for mineral_id, requirement in mineral_requirements.items():
        constraints[mineral_id] = solver.Constraint(requirement, solver.infinity())
        for ore_id, data in ore_data.items():
            if mineral_id in data['minerals']:
                constraints[mineral_id].SetCoefficient(ore_vars[ore_id], float(data['minerals'][mineral_id]) * efficiency)

    # Solve the problem
    status = solver.Solve()

    # Process and display the results
    if status == pywraplp.Solver.OPTIMAL:
        st.success("Optimal solution found!")
        result = ""
        total_cost = 0
        for ore_id, ore_var in ore_vars.items():
            ore_amount = ore_var.solution_value()
            if ore_amount > 0:
                ore_name = ore_data[ore_id]['name']
                refined_amount = ceil(ore_amount) * 100  # Round up to the nearest 100
                total_cost += refined_amount * float(market_data[str(ore_id)]['sell']['weightedAverage'])
                result += f"{ore_name} {refined_amount:,}\n"
        st.text_area("Optimized Ore List", value=result, height=200)
        st.write(f"Total Cost: {total_cost:,.2f} ISK")
    else:
        st.error("The solver could not find an optimal solution.")

# Streamlit app
st.title("EVE Online Compressed Ore Optimization")

# User input for mineral requirements
st.header("Input Mineral Requirements")
input_text = st.text_area("Paste your mineral requirements here (e.g., 'Tritanium 10000'):")

minerals = {
    'Tritanium': 34,
    'Pyerite': 35,
    'Mexallon': 36,
    'Isogen': 37,
    'Nocxium': 38,
    'Zydrine': 39,
    'Megacyte': 40,
    'Morphite': 11399
}

mineral_requirements = {}
if input_text:
    lines = input_text.split('\n')
    for line in lines:
        if line.strip():
            parts = line.split()
            if len(parts) >= 2:
                mineral_name = parts[0]
                quantity = int(parts[1].replace(",", ""))
                if mineral_name in minerals:
                    mineral_requirements[minerals[mineral_name]] = quantity

# Load data
ore_data = load_data('/workspaces/compressionoptimizer/refineMaterials.csv', '/workspaces/compressionoptimizer/invTypes_2024.csv')

# Optimize button
if st.button("Optimize"):
    try:
        # Fetch market data
        type_ids = list(ore_data.keys())
        market_data = get_market_data(type_ids)

        # Optimize ores
        optimize_ores(ore_data, market_data, mineral_requirements)
    except Exception as e:
        st.error(f"An error occurred: {e}")
