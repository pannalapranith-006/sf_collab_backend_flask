# app/jobs/rp_job_commands.py

import click
from datetime import date, timedelta
from flask.cli import AppGroup

batch_cli = AppGroup('batch', help='Run batch jobs.')

@batch_cli.command('daily-metrics')
@click.option('--date', 'run_date', default=None, help='Date in YYYY-MM-DD (default today)')
def run_daily_metrics(run_date):
    from app.services.rp_batch_jobs import daily_metric_builder
    if run_date:
        run_date = date.fromisoformat(run_date)
    else:
        run_date = date.today()
    daily_metric_builder(run_date)
    click.echo(f'Daily metrics job for {run_date} completed.')

@batch_cli.command('warning-summary')
@click.option('--date', 'run_date', default=None)
def run_warning_summary(run_date):
    from app.services.rp_batch_jobs import warning_summary_job
    if run_date:
        run_date = date.fromisoformat(run_date)
    else:
        run_date = date.today()
    warning_summary_job(run_date)
    click.echo('Warning summary job completed.')

@batch_cli.command('revenue-pool-close')
@click.option('--date', 'run_date', default=None)
def run_revenue_pool_close(run_date):
    from app.services.rp_batch_jobs import revenue_pool_close
    if run_date:
        run_date = date.fromisoformat(run_date)
    else:
        run_date = date.today()
    revenue_pool_close(run_date)
    click.echo('Revenue pool closed.')

@batch_cli.command('payout-calculation')
@click.option('--date', 'run_date', default=None)
def run_payout_calc(run_date):
    from app.services.rp_batch_jobs import payout_calculation_job
    if run_date:
        run_date = date.fromisoformat(run_date)
    else:
        run_date = date.today()
    payout_calculation_job(run_date)
    click.echo('Payout calculation job completed.')

@batch_cli.command('weekly-summary')
@click.option('--week-start', default=None, help='Start of week in YYYY-MM-DD (default this Monday)')
def run_weekly_summary(week_start):
    from app.services.rp_batch_jobs import weekly_summary_builder
    if week_start:
        wk = date.fromisoformat(week_start)
    else:
        today = date.today()
        wk = today - timedelta(days=today.weekday())  # Monday
    weekly_summary_builder(wk)
    click.echo('Weekly summary built.')
