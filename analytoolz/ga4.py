"""
Functions for Google Analytics 4 API
"""

from datetime import datetime
import pandas as pd
import pytz
import re
import sys

from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.admin_v1alpha.types import CustomDimension
from google.analytics.admin_v1alpha.types import CustomMetric
from google.analytics.admin_v1alpha.types import DataRetentionSettings
from google.analytics.admin_v1alpha.types import IndustryCategory
from google.analytics.admin_v1alpha.types import ServiceLevel
from google.analytics.data import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import Dimension
from google.analytics.data_v1beta.types import Filter
from google.analytics.data_v1beta.types import FilterExpression
from google.analytics.data_v1beta.types import FilterExpressionList
from google.analytics.data_v1beta.types import Metadata
from google.analytics.data_v1beta.types import Metric
from google.analytics.data_v1beta.types import MetricAggregation
from google.analytics.data_v1beta.types import MetricType
from google.analytics.data_v1beta.types import OrderBy
from google.analytics.data_v1beta.types import RunReportRequest
from google.analytics.data_v1beta.types import RunReportResponse
from google.api_core.exceptions import PermissionDenied
from google.oauth2.credentials import Credentials

from . import utils


class RoboGA4:
    required_scopes = [
        'https://www.googleapis.com/auth/analytics.edit',
        'https://www.googleapis.com/auth/analytics.readonly',
    ]

    def __init__(self, credentials, **kwargs):  # *args,
        """constructor"""
        self.credentials = credentials
        self.data_client = None
        self.admin_client = None
        self.account = self.Account(self)
        self.property = self.Property(self)
        self.report = self.Report(self)
        if credentials:
            self.authorize()

    def _parse_account_path(self, path: str):
        dict = self.admin_client.parse_account_path(path)
        return dict.get('account')

    def _parse_property_path(self, path: str):
        dict = self.admin_client.parse_property_path(path)
        return dict.get('property')

    def authorize(self):
        if isinstance(self.credentials, Credentials):
            print("Launching RoboGA4")
            self.data_client = BetaAnalyticsDataClient(credentials=self.credentials)
            self.admin_client = AnalyticsAdminServiceClient(credentials=self.credentials)
        else:
            print("credentials given are invalid.")
            return
        if bool(set(self.credentials.scopes) & set(self.required_scopes)):
            # print("scopes look good")
            pass
        else:
            print("the given scopes don't meet requirements.")
            return

    class Account:
        def __init__(self, parent):
            self.parent = parent
            self.id = None

        def select(self, id: str):
            self.id = id

        def list(self):
            """Returns summaries of all accounts accessible by the caller."""
            try:
                results_iterator = self.parent.admin_client.list_account_summaries()
            except PermissionDenied as e:
                print("権限がありません。")
                message = getattr(e, 'message', repr(e))
                ex_value = sys.exc_info()[1]
                m = re.search(r'reason: "([^"]+)', str(ex_value))
                if m:
                    reason = m.group(1)
                if reason == 'SERVICE_DISABLED':
                    print("GCPのプロジェクトでAdmin APIを有効化してください。")
                print(message)
            except Exception as e:
                # print(e)
                type_, value, traceback_ = sys.exc_info()
                print(type_)
                print(value)
            else:
                list = []
                for item in results_iterator:
                    dict = {
                        'id': self.parent._parse_account_path(item.account),
                        'name': item.display_name,
                        'properties': [],
                    }
                    for p in item.property_summaries:
                        prop = {
                            'id': self.parent._parse_property_path(p.property),
                            'name': p.display_name
                        }
                        dict['properties'].append(prop)
                    list.append(dict)
                return list

    class Property:
        def __init__(self, parent):
            self.parent = parent
            self.id = None

        def select(self, id: str):
            self.id = id

        def info(self):
            properties = self.list()
            return [p for p in properties if p['id'] == self.id][0]

        def list(self):
            """Returns summaries of all properties for the account"""
            try:
                results_iterator = self.parent.admin_client.list_properties({
                    'filter': f"parent:accounts/{self.parent.account.id}",
                    'show_deleted': False,
                })
            except Exception as e:
                print(e)
            else:
                list = []
                for item in results_iterator:
                    dict = {
                        'id': self.parent._parse_property_path(item.name),
                        'name': item.display_name,
                        'time_zone': item.time_zone,
                        'currency': item.currency_code,
                        'industry': IndustryCategory(item.industry_category).name,
                        'service_level': ServiceLevel(item.service_level).name,
                        'created_time': datetime.fromtimestamp(
                            item.create_time.timestamp(),
                            pytz.timezone('Asia/Tokyo')
                        ),
                        'updated_time': datetime.fromtimestamp(
                            item.update_time.timestamp(),
                            pytz.timezone('Asia/Tokyo')
                        )
                    }
                    list.append(dict)
                return list

        def data_retention(self):
            """Returns data retention settings for the property."""
            try:
                item = self.parent.admin_client.get_data_retention_settings(
                    name=f"properties/{self.id}/dataRetentionSettings")
            except Exception as e:
                print(e)
            else:
                dict = {
                    'data_retention': DataRetentionSettings.RetentionDuration(item.event_data_retention).name,
                    'reset_user_data_on_new_activity': item.reset_user_data_on_new_activity,
                }
                return dict

        def available(self):
            """Returns available custom dimensions and custom metrics for the property."""
            path = self.parent.data_client.metadata_path(self.id)
            try:
                response = self.parent.data_client.get_metadata(name=path)
            except Exception as e:
                print(e)
            else:
                dimensions = []
                for i in response.dimensions:
                    dimensions.append({
                        'customized': i.custom_definition,
                        'category': i.category,
                        'api_name': i.api_name,
                        'display_name': i.ui_name,
                        'description': i.description,
                        # 'deprecated_api_names': i.deprecated_api_names,
                    })
                metrics = []
                for i in response.metrics:
                    metrics.append({
                        'customized': i.custom_definition,
                        'category': i.category,
                        'api_name': i.api_name,
                        'display_name': i.ui_name,
                        'description': i.description,
                        # 'deprecated_api_names': i.deprecated_api_names,
                        'type': i.type_,
                        'expression': i.expression,
                    })
                return {'dimensions': dimensions, 'metrics': metrics}

        def list_custom_dimensions(self):
            """Returns custom dimensions for the property."""
            try:
                results_iterator = self.parent.admin_client.list_custom_dimensions(
                    parent=f"properties/{self.id}")
            except Exception as e:
                print(e)
            else:
                list = []
                for item in results_iterator:
                    dict = {
                        'parameter_name': item.parameter_name,
                        'display_name': item.display_name,
                        'description': item.description,
                        'scope': CustomDimension.DimensionScope(item.scope).name,
                        # 'disallow_ads_personalization': item.disallow_ads_personalization,
                    }
                    list.append(dict)
                return list

        def list_custom_metrics(self):
            """Returns custom metrics for the property."""
            try:
                results_iterator = self.parent.admin_client.list_custom_metrics(
                    parent=f"properties/{self.id}")
            except Exception as e:
                print(e)
            else:
                list = []
                for item in results_iterator:
                    dict = {
                        'parameter_name': item.parameter_name,
                        'display_name': item.display_name,
                        'description': item.description,
                        'scope': CustomDimension.DimensionScope(item.scope).name,
                        'measurement_unit': CustomMetric.MeasurementUnit(item.measurement_unit).name,
                        'restricted_metric_type': [CustomMetric.RestrictedMetricType(d).name for d in
                                                   item.restricted_metric_type],
                    }
                    list.append(dict)
                return list

        def show(
                self,
                me: str = 'properties',
                index_col: str = 'parameter_name'
        ):
            if me == 'custom_metrics':
                res = self.list_custom_metrics()
                if res:
                    df = pd.DataFrame(res)
                    if index_col:
                        return df.set_index(index_col)
            elif me == 'custom_dimensions':
                res = self.list_custom_dimensions()
                if res:
                    df = pd.DataFrame(res)
                    if index_col:
                        return df.set_index(index_col)
            elif me == 'properties':
                res = self.list()
                index_col = 'id'
            if res:
                df = pd.DataFrame(res)
                if index_col:
                    return df.set_index(index_col)

            return pd.DataFrame()

        def create_custom_dimension(
                self,
                parameter_name: str,
                display_name: str,
                description: str,
                scope: str = 'EVENT'
        ):
            """Create custom dimension for the property."""
            try:
                created_cd = self.parent.admin_client.create_custom_dimension(
                    parent=f"properties/{self.id}",
                    custom_dimension={
                        'parameter_name': parameter_name,
                        'display_name': display_name,
                        'description': description,
                        'scope': CustomDimension.DimensionScope[scope].value,
                    }
                )
                return created_cd
            except Exception as e:
                print(e)

    class Report:
        def __init__(self, parent):
            self.parent = parent
            self.date_start = '7daysAgo'
            self.date_end = 'yesterday'

        def set_dates(self, date_start: str, date_end: str):
            self.date_start = date_start
            self.date_end = date_end

        def _ga4_response_to_dict(self, response: RunReportResponse):
            dim_len = len(response.dimension_headers)
            metric_len = len(response.metric_headers)
            all_data = []
            for row in response.rows:
                row_data = {}
                for i in range(0, dim_len):
                    row_data.update({response.dimension_headers[i].name: row.dimension_values[i].value})
                for i in range(0, metric_len):
                    row_data.update({response.metric_headers[i].name: row.metric_values[i].value})
                all_data.append(row_data)
            # df = pd.DataFrame(all_data)
            # return df
            return all_data

        def _convert_metric(self, value, type: str):
            """Metric's Value types are
                METRIC_TYPE_UNSPECIFIED = 0
                TYPE_CURRENCY = 9
                TYPE_FEET = 10
                TYPE_FLOAT = 2
                TYPE_HOURS = 7
                TYPE_INTEGER = 1
                TYPE_KILOMETERS = 13
                TYPE_METERS = 12
                TYPE_MILES = 11
                TYPE_MILLISECONDS = 5
                TYPE_MINUTES = 6
                TYPE_SECONDS = 4
                TYPE_STANDARD = 8
            """
            if type in ['TYPE_INTEGER', 'TYPE_HOURS','TYPE_MINUTES','TYPE_SECONDS','TYPE_MILLISECONDS']:
                return int(value)
            elif type in ['TYPE_FLOAT']:
                return float(value)
            else:
                return value

        def _parse_ga4_response(self, response: RunReportResponse):
            names = []
            dimension_types = []
            metrics_types = []

            for i in response.dimension_headers:
                names.append(i.name)
                dimension_types.append('category')

            for i in response.metric_headers:
                names.append(i.name)
                metrics_types.append(MetricType(i.type_).name)

            all_data = []
            for row in response.rows:
                row_data = []
                for d in row.dimension_values:
                    row_data.append(d.value)
                for i in range(0, len(row.metric_values)):
                    row_data.append(
                        self._convert_metric(
                            row.metric_values[i].value,
                            metrics_types[i]
                        )
                    )
                all_data.append(row_data)

            return all_data, names, dimension_types + metrics_types

        def _format_filter(self, conditions, logic=None):
            if logic == 'AND':
                return FilterExpression(
                    and_group=FilterExpressionList(
                        expressions=[
                            FilterExpression(
                                filter=Filter(
                                    field_name="platform",
                                    string_filter=Filter.StringFilter(
                                        match_type=Filter.StringFilter.MatchType.EXACT,
                                        value="Android",
                                    ),
                                )
                            ),
                        ]
                    )
                )
            elif logic == 'OR':
                return FilterExpression(
                    or_group=FilterExpressionList(
                        expressions=[
                            FilterExpression(
                                filter=Filter()
                            ),
                        ]
                    )
                )
            elif logic == 'NOT':
                return FilterExpression(
                    not_expression=FilterExpression(
                        filter=Filter()
                    )
                )
            else:
                return FilterExpression(
                    filter=Filter()
                )

        def _call_api(
                self,
                dimensions: list,
                metrics: list,
                dimension_filter=None,
                metric_filter=None,
                order_bys=None,
                show_total: bool = False,
                limit: int = 0,
                offset: int = 0,
        ):
            dimensions_ga4 = []
            for dimension in dimensions:
                dimensions_ga4.append(Dimension(name=dimension))

            metrics_ga4 = []
            for metric in metrics:
                metrics_ga4.append(Metric(name=metric))

            metric_aggregations = []
            if show_total:
                metric_aggregations = [
                    MetricAggregation.TOTAL,
                    MetricAggregation.MAXIMUM,
                    MetricAggregation.MINIMUM,
                ]

            request = RunReportRequest(
                property=f"properties/{self.parent.property.id}",
                dimensions=dimensions_ga4,
                metrics=metrics_ga4,
                date_ranges=[DateRange(start_date=self.date_start, end_date=self.date_end)],
                dimension_filter=dimension_filter,
                metric_filter=metric_filter,
                order_bys=order_bys,
                limit=limit,
                offset=offset,
            )

            data = []
            headers = []
            types = []
            row_count = 0
            response = None
            try:
                response = self.parent.data_client.run_report(request)
                row_count = response.row_count
            except PermissionDenied as e:
                print("権限がありません。")
                message = getattr(e, 'message', repr(e))
                ex_value = sys.exc_info()[1]
                m = re.search(r'reason: "([^"]+)', str(ex_value))
                if m:
                    reason = m.group(1)
                if reason == 'SERVICE_DISABLED':
                    print("GCPのプロジェクトでData APIを有効化してください。")
                print(message)
            except Exception as e:
                # print(e)
                type_, value, traceback_ = sys.exc_info()
                print(type_)
                print(value)

            if row_count > 0:
                data, headers, types = self._parse_ga4_response(response)

            return data, row_count, headers, types

        def run(
                self,
                dimensions: list,
                metrics: list,
                dimension_filter=None,
                metric_filter=None,
                order_bys=None,
                show_total: bool = False,
                limit: int = 10000,
                to_pd: bool = True
        ):
            offset = 0
            all_rows = []
            headers = []
            types = []
            page = 1

            while True:
                (data, row_count, headers, types) = self._call_api(
                    dimensions,
                    metrics,
                    dimension_filter=dimension_filter,
                    metric_filter=metric_filter,
                    order_bys=order_bys,
                    show_total=show_total,
                    limit=limit,
                    offset=offset
                )
                if len(data) > 0:
                    all_rows.extend(data)
                    print(f"p{page}: retrieved #{offset + 1} - #{offset + len(data)}")
                    if offset + len(data) == row_count:
                        break
                    else:
                        page += 1
                        offset += limit
                else:
                    break

            if len(all_rows) > 0:
                print(f"\nTotal: {len(all_rows)} rows")
            else:
                print("no data found.")

            if to_pd:
                df = pd.DataFrame(all_rows, columns=headers)
                df = utils.change_column_type(df)
                return df
            else:
                return all_rows, headers, types

        """
        reports
        """
        def pv_by_day(self):
            dimensions = [
                'date',
                'eventName',
            ]
            metrics = [
                'eventCount',
            ]
            dimension_filter = FilterExpression(
                filter=Filter(
                    field_name="eventName",
                    string_filter=Filter.StringFilter(value="page_view"),
                )
            )
            order_bys = [
                OrderBy(
                    desc=False,
                    dimension=OrderBy.DimensionOrderBy(
                        dimension_name="date"
                    )
                ),
            ]
            return self.run(
                dimensions,
                metrics,
                dimension_filter=dimension_filter,
                order_bys=order_bys
            )

        def events_by_day(self):
            dimensions = [
                'date',
                'eventName',
            ]
            metrics = [
                'eventCount',
            ]
            # dimension_filter = FilterExpression(
            #     filter=Filter(
            #         field_name="eventName",
            #         string_filter=Filter.StringFilter(value="page_view"),
            #     )
            # )
            # dimension_filter = FilterExpression(
            #     not_expression=FilterExpression(
            #     filter=Filter(
            #         field_name="eventName",
            #         numeric_filter=Filter.NumericFilter(
            #             operation=Filter.NumericFilter.Operation.GREATER_THAN,
            #             value=NumericValue(int64_value=1000),
            #         ),
            #     )
            #     )
            # )
            # dimension_filter = FilterExpression(
            #     filter=Filter(
            #         field_name="eventName",
            #         in_list_filter=Filter.InListFilter(
            #             values=[
            #                 "purchase",
            #                 "in_app_purchase",
            #                 "app_store_subscription_renew",
            #             ]
            #         ),
            #     )
            # )
            # dimension_filter = FilterExpression(
            #     and_group=FilterExpressionList(
            #         expressions=[
            #             FilterExpression(
            #                 filter=Filter(
            #                     field_name="browser",
            #                     string_filter=Filter.StringFilter(value="Chrome"),
            #                 )
            #             ),
            #             FilterExpression(
            #                 filter=Filter(
            #                     field_name="countryId",
            #                     string_filter=Filter.StringFilter(value="US"),
            #                 )
            #             ),
            #         ]
            #     )
            # )
            order_bys = [
                OrderBy(
                    desc=False,
                    dimension=OrderBy.DimensionOrderBy(
                        dimension_name="date"
                    )
                ),
                OrderBy(
                    desc=True,
                    metric=OrderBy.MetricOrderBy(
                        metric_name="eventCount"
                    )
                ),
            ]
            return self.run(
                dimensions,
                metrics,
                # dimension_filter=dimension_filter,
                order_bys=order_bys
            )

        def pv(self):
            dimensions = [
                # 'customUser:gtm_client_id',
                # 'customUser:ga_client_id',
                # 'customEvent:ga_session_number',
                # 'city',
                # 'customEvent:local_datetime',
                'eventName',
                'pagePath',
            ]
            metrics = [
                'eventCount',
                # 'customEvent:entrances',
                # 'customEvent:engagement_time_msec',
            ]
            (data, headers, types) = self.run(dimensions, metrics)

            return headers, data
