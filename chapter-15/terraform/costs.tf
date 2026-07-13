# Terraform — AWS Budgets for Monthly Cost Alerts
# Chapter 15: The Cost of Scale
# Budget alerts at 50%, 80%, 100% of monthly forecast.
# Principle: "Cost is a metric. Review it regularly."

resource "aws_budgets_budget" "beacon_monthly" {
  name              = "beacon-monthly-${var.project_id}"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget_limit
  limit_unit        = "USD"
  time_period_start = "2025-01-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["infra@beacon.internal"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["infra@beacon.internal", "engineering-leads@beacon.internal"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "FORECASTED"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = ["infra@beacon.internal", "cto@beacon.internal"]
  }

  tags = { Chapter = "15" }
}

variable "monthly_budget_limit" {
  description = "Maximum monthly AWS spend before alerting"
  type        = number
  default     = 160000  # $160k/month target post-optimizations
}
