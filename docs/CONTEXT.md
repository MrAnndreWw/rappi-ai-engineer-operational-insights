# Competitive Intelligence System for Rappi

## Overview

This project consists of building an automated **competitive intelligence system** for Rappi.

Rappi operates in a highly dynamic market where competitors such as Uber Eats and DiDi Food constantly change:

* Prices
* Delivery times
* Fees
* Promotions

Currently, there is no systematic visibility into how Rappi compares against competitors in these variables.

### Goal

Build a system that:

1. Collects competitive data automatically
2. Structures and stores it
3. Generates actionable insights for Strategy, Pricing, and Operations teams

---

## Target entry URLs (Mexico)

Browser entry points for location-based flows (address first, then search). Use clean URLs in config (omit tracking query params such as `srsltid`).

| Platform | URL |
|----------|-----|
| Rappi (baseline) | https://www.rappi.com.mx |
| Uber Eats | https://www.ubereats.com/mx |
| DiDi Food | https://www.didi-food.com/es-MX/food/ |

---

## Problem Statement

The system should answer questions like:

* Is Rappi more expensive or cheaper than competitors in each zone?
* Are delivery times competitive?
* How do service fees compare?
* What promotions are competitors running?

---

## Deliverables

### 1. Competitive Scraping System (70%)

Build a system that collects data from:

* Rappi (baseline)
* Uber Eats
* DiDi Food

#### Requirements

##### Data Collection

* Scrape data from at least **2 competitors + Rappi**
* Cover **20–50 representative addresses**
* Document and justify selected addresses

##### Metrics (collect at least 3)

* Product price (3–5 comparable items)
* Delivery fee
* Service fee
* Estimated delivery time
* Active discounts/promotions
* Availability (open/closed stores)
* Final total price

##### Standardized Products

Use comparable products such as:

* Big Mac / Whopper
* Combo meal
* Nuggets
* Coca-Cola 500ml
* Water 1L
* Diapers (recognized brand)

##### Automation

* Must run via script/command
* Output structured data (CSV or JSON)

---

### 2. Competitive Insights Report (30%)

Generate an analytical report based on the scraped data.

#### Required Analysis

* Price positioning (cheaper / more expensive / similar)
* Delivery time comparison
* Fee structure comparison
* Promotion strategy analysis
* Geographic variability

#### Top 5 Insights

Each insight must include:

* **Finding**: what was discovered
* **Impact**: why it matters
* **Recommendation**: what Rappi should do

#### Visualizations

* At least 3 charts
* Clear comparisons (bar charts, tables, heatmaps)

#### Output Format

* PDF, dashboard, or similar
* Must be actionable

---

## Technical Requirements

### Stack

Flexible, but recommended:

* Python
* Scraping: Playwright / Selenium / BeautifulSoup / Scrapy
* Analysis: pandas, matplotlib
* Optional: Streamlit or dashboards

### System Requirements

* Reproducible execution
* Clear setup instructions
* Modular and maintainable code

### Expected Outputs

* Raw data (CSV/JSON)
* Final report
* Documentation

---

## Architecture Expectations

The system should be structured in layers:

1. **Scraping layer**

   * Independent scrapers per platform

2. **Data processing layer**

   * Cleaning and normalization
   * Standard schema across platforms

3. **Storage layer**

   * Structured datasets

4. **Analysis layer**

   * Comparative logic
   * Insight generation

5. **Reporting layer**

   * Visualizations
   * Final report

The architecture should allow:

* Adding new competitors easily
* Scaling to more products or locations

---

## Constraints and Scope

* Time is limited → prioritize a realistic scope
* Prefer **quality over quantity**
* Better:

  * 5 addresses well scraped
  * than 50 poorly implemented

---

## Best Practices

* Use rate limiting (avoid blocking)
* Handle scraping failures gracefully
* Log errors and retries
* Keep code modular
* Document limitations clearly

---

## Ethical Considerations

* Respect robots.txt when possible
* Do not overload servers
* Use reasonable request rates
* Document any limitations or constraints

---

## Evaluation Criteria

* Scraping quality and robustness (50%)
* Insight quality (15%)
* Technical design (10%)
* Documentation (5%)
* Presentation (20%)

---

## Expected Repository Structure (High-Level)

The project should be organized clearly, separating:

* scrapers per platform
* data processing
* analysis
* reporting
* configuration
* outputs

---

## Execution Expectations

The evaluator should be able to:

1. Install dependencies
2. Run scraping with a command
3. Generate the report
4. Review outputs easily

---

## Final Notes

* Start simple and iterate
* Focus on actionable insights
* Be pragmatic
* Clearly document trade-offs and limitations

This project is meant to simulate a real-world business problem under time constraints.
