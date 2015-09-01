#!/usr/bin/env python

##
##  Copyright 2015 SRI International
##  License: https://ncanda.sri.com/software-license.txt
##
##  $Revision$
##  $LastChangedBy$
##  $LastChangedDate$
##
"""
Neuroradiology Findings

Script to sync and generate reports on findings from radiology readings

Examples
========
- Findings and Findings Date is empty before a given date
./neurorad_findings --update --report-type no_findings_before_date --before-date 2015-06-08
"""
__author__ = 'Nolan Nichols <https://orcid.org/0000-0003-1099-3328>'
__modified__ = "2015-08-31"

import os

import pandas as pd

import xnat_extractor as xe

verbose = None


def set_experiment_attrs(config, project, subject, experiment, key, value):
    """
    Set the field for an MRSession

    For example, datetodvd, findingsdate, findings
    :param config: str
    :param project: str
    :param subject: str
    :param experiment: str
    :param key: str
    :param value: str
    :return: str
    """
    config = xe.get_config(config)
    session = xe.get_xnat_session(config)
    api = config.get('api')
    path = '{}/projects/{}/subjects/{}/experiments/{}'.format(api, project, subject, experiment)
    xsi = 'xnat:mrSessionData'
    field = 'xnat:mrSessionData/fields/field[name={}]/field'.format(key)
    payload = {'xsiType': xsi, field: value}
    return session.put(path, params=payload)


def update_findings_date(config, merged_findings):
    """
    For all records found, set the findings date attribute to datatodvd

    :param config: dict
    :param merged_findings: pd.DataFrame
    :return:
    """
    for idx, row in merged_findings.iterrows():
        result = set_experiment_attrs(config, row.project, row.subject_id, row.experiment_id, 'findingsdate', row.datetodvd)
        if verbose:
            print("Updated experiment: {}".format(result))
    return


def findings_date_empty(df):
    """
    Find all experiments that have a finding recorded but no date entered.

    :param df: pd.DataFrame
    :return: pd.DataFrame
    """
    has_finding = df[~df.findings.isnull()]
    no_findings_date = has_finding[has_finding.findingsdate.isnull()]
    return no_findings_date


def findings_empty(df):
    """
    Find all experiments that have a finding date recorded but no finding entered.

    :param df: pd.DataFrame
    :return: pd.DataFrame
    """
    has_findings_date = df[~df.findingsdate.isnull()]
    no_findings_date = has_findings_date[has_findings_date.findings.isnull()]
    return no_findings_date


def findings_and_date_empty(df):
    """
    Find all experiments that have empty findings date and findings.

    :param df: pd.DataFrame
    :return: pd.DataFrame
    """
    no_findings_or_date = df[(df.findings.isnull()) & (df.findingsdate.isnull())]
    return no_findings_or_date


def check_dvdtodate_before_date(df, before_date=None):
    """
    Find all experiments that have a datetodvd before a given date.
    Also convert date from string to datetime (YYYY-MM-DD)

    :param df: pd.DataFrame
    :return: pd.DataFrame
    """
    has_datetodvd = df[~df.datetodvd.isnull()]
    has_datetodvd.loc[:, 'datetodvd'] = has_datetodvd.datetodvd.astype('datetime64')
    date = pd.Timestamp(before_date)
    return has_datetodvd[has_datetodvd.datetodvd < date]


def inner_join_dataframes(df1, df2):
    """
    Join two dataframes using an inner join

    :param df1: pd.DataFrame
    :param df2: pd.DataFrame
    :return: pd.DataFrame
    """
    return pd.merge(df1, df2, how='inner')


def main(args=None):
    if args.update:
        # Update the cache of XNAT Experiment XML files
        config = xe.get_config(args.config)
        session = xe.get_xnat_session(config)
        xe.extract_experiment_xml(config, session,
                                  args.experimentsdir, args.num_extract)

    # extract info from the experiment XML files
    experiment = xe.get_experiments_dir_info(args.experimentsdir)
    experiment_df = xe.experiments_to_dataframe(experiment)
    reading = xe.get_experiments_dir_reading_info(args.experimentsdir)
    reading_df = xe.reading_to_dataframe(reading)
    experiment_reading = inner_join_dataframes(experiment_df, reading_df)

    # exclude phantoms, but include the traveling human phantoms
    site_id_pattern = '[A-EX]-[0-9]{5}-[MFT]-[0-9]'
    df = experiment_reading[experiment_reading.site_id.str.contains(site_id_pattern)]

    result = None
    if args.report_type == 'no_findings_date':
        # Findings are listed without a findings date
        result = findings_date_empty(df)
        if args.set_findings_date:
            # Update the findings date to equal the date to dvd
            update_findings_date(args.config, result)

    if args.report_type == 'no_findings':
        # Findings is empty but a date is listed
        result = findings_empty(df)

    if args.report_type == 'no_findings_or_date':
        # Both the findings and findings date are empty
        result = findings_and_date_empty(df)

    if args.report_type == 'no_findings_before_date':
        # Findings and Findings Date is empty before a given date
        if not args.before_date:
            raise(Exception("Please set --before-date YYYY-MM-DD when running the no_findings_before_date report."))
        has_dvd_before_date = check_dvdtodate_before_date(df, before_date=args.before_date)
        result = findings_and_date_empty(has_dvd_before_date)
        result.to_csv(args.outfile, index=False)

    result.to_csv(args.outfile,
                  columns=['project', 'subject_id', 'experiment_id',
                           'site_experiment_id', 'datetodvd', 'findingsdate'],
                  index=False)

if __name__ == "__main__":
    import sys
    import argparse

    formatter = argparse.RawDescriptionHelpFormatter
    default = 'default: %(default)s'
    parser = argparse.ArgumentParser(prog="neurorad_findings.py",
                                     description=__doc__,
                                     formatter_class=formatter)
    parser.add_argument('-b', '--before-date',
                        type=str,
                        help='To be used with --report_type no_findings_before_date. YYYY-MM-DD')
    parser.add_argument('-c', '--config',
                        type=str,
                        default=os.path.join(os.path.expanduser('~'),
                                             '.server_config', 'ncanda.cfg'))
    parser.add_argument('-e', '--experimentsdir',
                        type=str,
                        default='/tmp/experiments',
                        help='Name of experiments xml directory')
    parser.add_argument('-o', '--outfile',
                        type=str,
                        default='/tmp/neurorad_findings.csv',
                        help='Name of csv file to write.')
    parser.add_argument('-n', '--num-extract',
                        type=int,
                        help='Number of sessions to extract')
    parser.add_argument('-r', '--report-type',
                        type=str,
                        choices=['no_findings_date', 'no_findings', 'no_findings_or_date', 'no_findings_before_date'],
                        help='Select a report type. Note that no_findings_before_date requires --before_date.')
    parser.add_argument('-s', '--set-findings-date',
                        action='store_true',
                        help='If findings are reported and the findings date is None then set it to the date of dvd.')
    parser.add_argument('-u', '--update',
                        action='store_true',
                        help='Update the cache of xml files')
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='Print verbose output.')

    argv = parser.parse_args()

    verbose = argv.verbose
    xe.verbose = argv.verbose
    sys.exit(main(args=argv))