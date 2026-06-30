variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "scrimterz-bangkok-urban"
}

variable "region" {
  description = "Default Region for GCP Resources"
  type        = string
  default     = "asia-southeast1" # Low-cost standard region
}

variable "storage_class" {
  description = "Storage Class for GCS Buckets"
  type        = string
  default     = "STANDARD"
}