
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from io import BytesIO

st.set_page_config(page_title="FIRE Estimator - User Sliders", layout="wide")
st.title("FIRE Estimator — Interactive Sliders")

# --- Sidebar: basic controls ---
st.sidebar.header("Controls")
start_year = st.sidebar.number_input("Start Year", value=2025, min_value=2023, max_value=2040, step=1)
start_age = st.sidebar.number_input("Age as on Start Year", value=40, min_value=18, max_value=100, step=1)
end_age = st.sidebar.number_input("Life Expectancy (Age)", value=80, min_value=start_age+1, max_value=120, step=1)
buffer_inr = st.sidebar.number_input("FIRE Buffer (INR)", value=5_000_000, min_value=0, step=100000)

# Grouped input using expanders
st.header("Inputs (grouped)")

with st.expander("Basis"):
    st.write("Rates, inflation, FX, rental baseline")
    rental_monthly_upto_2035 = st.number_input("Rental monthly upto 2035 (INR)", value=20000, step=1000)
    rental_monthly_after_2035 = st.number_input("Rental monthly after 2035 (INR)", value=30000, step=1000)
    rental_increase = st.number_input("Rental increase % per year", value=2.5, step=0.1) / 100.0
    inflation_india = st.number_input("Indian inflation %", value=10.0, step=0.1) / 100.0
    inflation_us = st.number_input("US inflation %", value=3.0, step=0.1) / 100.0
    usd_inr_rate0 = st.number_input("USD to INR (starting)", value=88.0, step=0.1)
    usd_inr_growth = st.number_input("USD/INR growth % per year", value=3.0, step=0.1) / 100.0

    st.subheader("Returns (annual %)")
    indian_stocks_r = st.number_input("Indian Stocks & ETF", value=12.0, step=0.1) / 100.0
    indian_mf_r = st.number_input("Indian Mutual Fund", value=12.0, step=0.1) / 100.0
    indian_bonds_r = st.number_input("Indian Bonds", value=9.0, step=0.1) / 100.0
    indian_fd_r = st.number_input("Indian Fixed Deposit", value=7.0, step=0.1) / 100.0
    us_stocks_r = st.number_input("US Stocks & ETF", value=8.0, step=0.1) / 100.0
    us_mf_r = st.number_input("US Mutual Fund", value=8.0, step=0.1) / 100.0
    us_bonds_r = st.number_input("US Bonds", value=4.0, step=0.1) / 100.0
    us_fd_r = st.number_input("US FD", value=4.0, step=0.1) / 100.0

with st.expander("Investments"):
    st.write("Initial balances (INR unless USD specified)")
    bond_india = st.number_input("Bond India (INR)", value=1_000_000, step=10000)
    sbi_locked = st.number_input("Bank locked (INR) — locked until year", value=1_000_000, step=10000)
    sbi_lock_until = st.number_input("Bank unlocked year", value=2045, step=1)
    fd_india = st.number_input("Fixed Deposit India (INR)", value=1_000_000, step=1000)
    mf_india = st.number_input("Mutual Fund India (INR)", value=1_000_000, step=1000)
    stocks_india = st.number_input("Indian Stocks & ETF (INR)", value=1_000_000, step=1000)
    us_stocks_usd = st.number_input("US Stocks & ETF (USD)", value=10_000, step=100)
    us_fd_usd = st.number_input("US Fixed Deposit (USD)", value=10_000, step=100)
    us_bonds_usd = st.number_input("US Bonds (USD)", value=1_000, step=10)

with st.expander("Expenditure"):
    living_monthly = st.number_input("Living Expense (INR/month)", value=50_000, step=1000)
    travel_yearly = st.number_input("Travel (INR/year)", value=100_000, step=1000)
    travel_start = st.number_input("Travel start year", value=2026, step=1)
    travel_end = st.number_input("Travel end year", value=2036, step=1)
    insurance_yearly = st.number_input("Insurance (INR/year)", value=100_000, step=1000)
    house_repair_yearly = st.number_input("House Repair (INR/year)", value=100_000, step=1000)

    st.subheader("One-time expenses (enter year and amount)")
    # We'll allow the user to edit a JSON list of one-time events
    default_one_time = [
        {"year":2026,"label":"College Fees","amount_inr":100000},
        {"year":2027,"label":"College Fees","amount_inr":100000},
        {"year":2028,"label":"College Fees","amount_inr":100000},
        {"year":2029,"label":"College Fees","amount_inr":100000},
        {"year":2030,"label":"Abroad prep & Application","amount_inr":100000},
        {"year":2030,"label":"Abroad College Fees","amount_usd":50000},
        {"year":2031,"label":"Abroad College Fees","amount_usd":50000},
        {"year":2035,"label":"New Car Buying","amount_inr":1500000},
        {"year":2036,"label":"Marriage Expense","amount_inr":1500000},
    ]
    one_time_json = st.text_area("One-time events JSON (each event: year,label,amount_inr or amount_usd)",
                                value=str(default_one_time), height=200)
    try:
        one_time_events = eval(one_time_json)
    except Exception as e:
        st.error("Invalid JSON for one-time events. Edit carefully. Using defaults.")
        one_time_events = default_one_time

with st.expander("Reinvestment & Other"):
    reinvest_monthly_india = st.number_input("Reinvestment to Indian Stocks (INR/month)", value=25000, step=1000)
    reinvest_yearly_india = reinvest_monthly_india * 12.0

with st.expander("Tax slabs (INR annual)"):
    slab1 = st.number_input("Tax free up to (INR)", value=1200000, step=1000)
    slab2 = st.number_input("Tax 20% up to (INR)", value=2000000, step=1000)
    rate_slab2 = st.number_input("Tax rate for slab2 (%)", value=20.0, step=0.1)/100.0
    rate_slab3 = st.number_input("Tax rate above slab2 (%)", value=33.0, step=0.1)/100.0

# --- Simulation function ---
def compute_taxable(taxable, s1, s2, r2, r3):
    if taxable <= s1:
        return 0.0
    if taxable <= s2:
        return (taxable - s1) * r2
    return (s2 - s1) * r2 + (taxable - s2) * r3

def rental_for_year_func(y, start_year, rental_monthly_upto_2035, rental_monthly_after_2035, rental_increase):
    if y <= 2035:
        m = rental_monthly_upto_2035 * ((1 + rental_increase) ** (y - start_year))
    else:
        m = rental_monthly_after_2035 * ((1 + rental_increase) ** (y - 2036))
    return m * 12.0

def simulate_all(params):
    # Unpack params
    start_year = params['start_year']
    start_age = params['start_age']
    end_age = params['end_age']
    years = list(range(start_year, start_year + (end_age - start_age) + 1))
    usd_inr_rate0 = params['usd_inr_rate0']
    usd_inr_growth = params['usd_inr_growth']

    # assets (copy)
    A = {
        'bond_india': params['bond_india'],
        'sbi_locked': params['sbi_locked'],
        'fd_india': params['fd_india'],
        'mf_india': params['mf_india'],
        'stocks_india': params['stocks_india'],
        'us_stocks_usd': params['us_stocks_usd'],
        'us_fd_usd': params['us_fd_usd'],
        'us_bonds_usd': params['us_bonds_usd'],
    }
    rows = []
    for y in years:
        age = start_age + (y - start_year)
        # grow
        A['bond_india'] *= (1 + params['indian_bonds_r'])
        A['fd_india'] *= (1 + params['indian_fd_r'])
        A['mf_india'] *= (1 + params['indian_mf_r'])
        A['stocks_india'] *= (1 + params['indian_stocks_r'])
        A['sbi_locked'] *= (1 + params['indian_stocks_r'])  # same growth as stocks per user assumption earlier
        A['us_stocks_usd'] *= (1 + params['us_stocks_r'])
        A['us_fd_usd'] *= (1 + params['us_fd_r'])
        A['us_bonds_usd'] *= (1 + params['us_bonds_r'])

        usd_inr = usd_inr_rate0 * ((1 + usd_inr_growth) ** (y - start_year))
        rental_annual = rental_for_year_func(y, start_year, params['rental_monthly_upto_2035'], params['rental_monthly_after_2035'], params['rental_increase'])
        living = params['living_monthly'] * 12.0 * ((1 + params['inflation_india']) ** (y - start_year))
        travel = params['travel_yearly'] if (y >= params['travel_start'] and y <= params['travel_end']) else 0.0
        insurance = params['insurance_yearly']
        house_repair = params['house_repair_yearly']

        # one time events for this year
        one_time_total = 0.0
        for ev in params['one_time_events']:
            try:
                if int(ev['year']) == y:
                    if 'amount_inr' in ev and ev['amount_inr']:
                        one_time_total += float(ev['amount_inr'])
                    if 'amount_usd' in ev and ev['amount_usd']:
                        one_time_total += float(ev['amount_usd']) * usd_inr
            except Exception:
                continue

        annual_expenses = living + travel + insurance + house_repair + one_time_total
        # reinvest added at start of year
        A['stocks_india'] += params['reinvest_yearly_india']

        required_withdraw = max(annual_expenses - rental_annual, 0.0)
        us_total_inr = (A['us_stocks_usd'] + A['us_fd_usd'] + A['us_bonds_usd']) * usd_inr
        total_portfolio = A['bond_india'] + A['fd_india'] + A['mf_india'] + A['stocks_india'] + A['sbi_locked'] + us_total_inr
        available_for_withdraw = total_portfolio - (A['sbi_locked'] if y < params['sbi_lock_until'] else 0.0)
        max_withdrawable = max(available_for_withdraw - params['buffer_inr'], 0.0)
        actual_withdraw = min(required_withdraw, max_withdrawable)
        shortfall = required_withdraw - actual_withdraw
        withdrawn_breakdown = {'fd_india':0,'mf_india':0,'stocks_india':0,'bond_india':0,'us_fd_inr':0,'us_bonds_inr':0,'us_stocks_inr':0}

        def withdraw_from_inr(key, amount):
            amt = min(A[key], amount)
            A[key] -= amt
            return amt

        to_withdraw = actual_withdraw
        for key in ['fd_india','mf_india','stocks_india','bond_india']:
            if to_withdraw<=0: break
            w = withdraw_from_inr(key, to_withdraw)
            withdrawn_breakdown[key] += w
            to_withdraw -= w
        if to_withdraw>0:
            need_usd = to_withdraw / usd_inr
            usd_w = min(A['us_fd_usd'], need_usd)
            A['us_fd_usd'] -= usd_w
            withdrawn_breakdown['us_fd_inr'] += usd_w * usd_inr
            to_withdraw -= usd_w * usd_inr
        if to_withdraw>0:
            need_usd = to_withdraw / usd_inr
            usd_w = min(A['us_bonds_usd'], need_usd)
            A['us_bonds_usd'] -= usd_w
            withdrawn_breakdown['us_bonds_inr'] += usd_w * usd_inr
            to_withdraw -= usd_w * usd_inr
        if to_withdraw>0:
            need_usd = to_withdraw / usd_inr
            usd_w = min(A['us_stocks_usd'], need_usd)
            A['us_stocks_usd'] -= usd_w
            withdrawn_breakdown['us_stocks_inr'] += usd_w * usd_inr
            to_withdraw -= usd_w * usd_inr

        taxable_income = rental_annual + actual_withdraw
        tax_due = compute_taxable(taxable_income, params['slab1'], params['slab2'], params['rate_slab2'], params['rate_slab3'])
        max_tax_withdrawable = max_withdrawable - actual_withdraw
        tax_paid = min(tax_due, max_tax_withdrawable)
        tp = tax_paid
        for key in ['fd_india','mf_india','stocks_india','bond_india']:
            if tp<=0: break
            w = withdraw_from_inr(key, tp)
            withdrawn_breakdown[key] += w
            tp -= w
        if tp>0:
            need_usd = tp / usd_inr
            usd_w = min(A['us_fd_usd'], need_usd)
            A['us_fd_usd'] -= usd_w
            withdrawn_breakdown['us_fd_inr'] += usd_w * usd_inr
            tp -= usd_w * usd_inr
        if tp>0:
            need_usd = tp / usd_inr
            usd_w = min(A['us_bonds_usd'], need_usd)
            A['us_bonds_usd'] -= usd_w
            withdrawn_breakdown['us_bonds_inr'] += usd_w * usd_inr
            tp -= usd_w * usd_inr
        if tp>0:
            need_usd = tp / usd_inr
            usd_w = min(A['us_stocks_usd'], need_usd)
            A['us_stocks_usd'] -= usd_w
            withdrawn_breakdown['us_stocks_inr'] += usd_w * usd_inr
            tp -= usd_w * usd_inr

        us_total_inr = (A['us_stocks_usd'] + A['us_fd_usd'] + A['us_bonds_usd']) * usd_inr
        total_portfolio_after = A['bond_india'] + A['fd_india'] + A['mf_india'] + A['stocks_india'] + A['sbi_locked'] + us_total_inr
        rows.append({
            'year': y, 'age': age, 'usd_inr': usd_inr, 'rental_annual': rental_annual,
            'living': living, 'travel': travel, 'insurance': insurance, 'house_repair': house_repair,
            'one_time_total': one_time_total, 'annual_expenses': annual_expenses,
            'required_withdraw': required_withdraw, 'actual_withdraw': actual_withdraw, 'shortfall': shortfall,
            'taxable_income': taxable_income, 'tax_due': tax_due, 'tax_paid': tax_paid,
            'withdrawn_fd_india': withdrawn_breakdown['fd_india'],
            'withdrawn_mf_india': withdrawn_breakdown['mf_india'],
            'withdrawn_stocks_india': withdrawn_breakdown['stocks_india'],
            'withdrawn_bond_india': withdrawn_breakdown['bond_india'],
            'withdrawn_us_fd_inr': withdrawn_breakdown['us_fd_inr'],
            'withdrawn_us_bonds_inr': withdrawn_breakdown['us_bonds_inr'],
            'withdrawn_us_stocks_inr': withdrawn_breakdown['us_stocks_inr'],
            'total_portfolio_end': total_portfolio_after, 'available_for_withdraw_start': available_for_withdraw
        })

    df = pd.DataFrame(rows)
    min_port = df['total_portfolio_end'].min()
    success = (df['total_portfolio_end'] >= params['buffer_inr']).all()
    return df, success, min_port

# --- Run simulation on user inputs ---
params = {
    'start_year': start_year, 'start_age': start_age, 'end_age': end_age,
    'buffer_inr': buffer_inr,
    'rental_monthly_upto_2035': rental_monthly_upto_2035,
    'rental_monthly_after_2035': rental_monthly_after_2035,
    'rental_increase': rental_increase,
    'inflation_india': inflation_india, 'inflation_us': inflation_us,
    'usd_inr_rate0': usd_inr_rate0, 'usd_inr_growth': usd_inr_growth,
    'indian_stocks_r': indian_stocks_r, 'indian_mf_r': indian_mf_r, 'indian_bonds_r': indian_bonds_r, 'indian_fd_r': indian_fd_r,
    'us_stocks_r': us_stocks_r, 'us_mf_r': us_mf_r, 'us_bonds_r': us_bonds_r, 'us_fd_r': us_fd_r,
    'bond_india': bond_india, 'sbi_locked': sbi_locked, 'sbi_lock_until': sbi_lock_until,
    'fd_india': fd_india, 'mf_india': mf_india, 'stocks_india': stocks_india,
    'us_stocks_usd': us_stocks_usd, 'us_fd_usd': us_fd_usd, 'us_bonds_usd': us_bonds_usd,
    'living_monthly': living_monthly, 'travel_yearly': travel_yearly, 'travel_start': travel_start, 'travel_end': travel_end,
    'insurance_yearly': insurance_yearly, 'house_repair_yearly': house_repair_yearly,
    'one_time_events': one_time_events,
    'reinvest_yearly_india': reinvest_yearly_india,
    'slab1': slab1, 'slab2': slab2, 'rate_slab2': rate_slab2, 'rate_slab3': rate_slab3
}

df, success, min_port = simulate_all(params)

st.subheader("Simulation summary")
col1, col2, col3 = st.columns(3)
col1.metric("Top-up needed (INR)", value="0 (not auto-calculated here)")
col2.metric("Minimum portfolio observed (INR)", value=f"{min_port:,.0f}")
col3.metric("Buffer success", value=str(success))

st.subheader("Portfolio chart")
fig, ax = plt.subplots(figsize=(10,4))
ax.plot(df['year'], df['total_portfolio_end'], marker='o', label='Total Portfolio (INR)')
ax.plot(df['year'], [params['buffer_inr']] * len(df), linestyle='--', label='Buffer (INR)')
ax.plot(df['year'], df['annual_expenses'], linestyle=':', marker='s', label='Annual Expenses (INR)')
ax.set_xlabel("Year")
ax.set_ylabel("INR")
ax.grid(True)
ax.legend()
st.pyplot(fig)

st.subheader("Yearly table (first 20 rows)")
st.dataframe(df.head(20))

# Download buttons
# def to_excel_bytes(df):
    # output = BytesIO()
    # with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
       # df.to_excel(writer, index=False, sheet_name='yearly')
       # writer.save()
   # return output.getvalue()


# REVISED CODE in REV 2
import io
import pandas as pd

def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="FIRE")
    processed_data = output.getvalue()
    return processed_data
# REVISED CODE in REV 2

excel_bytes = to_excel_bytes(df)
st.download_button("Download Simulation Excel", data=excel_bytes, file_name="fire_simulation.xlsx")

# Also allow downloading chart image
buf = BytesIO()
fig.savefig(buf, format='png', bbox_inches='tight')
buf.seek(0)
st.download_button("Download Chart PNG", data=buf, file_name="portfolio_chart.png", mime="image/png")

st.markdown("**Notes:** This model uses simplified tax and withdrawal rules and assumes deterministic returns. Use for planning and sensitivity checks, not as financial advice Program developed by Sathish PT.")
