variable "vercel_api_token" {
  description = "Vercel API token; supply through TF_VAR_vercel_api_token, never commit it."
  type        = string
  sensitive   = true
}

variable "vercel_team_id" {
  description = "Optional Vercel team ID. Leave null for a personal account."
  type        = string
  default     = null
}

variable "project_name" {
  description = "Vercel project name."
  type        = string
  default     = "lamu-tours-booking-agency"
}