terraform {
  required_providers {
    vercel = {
      source  = "vercel/vercel"
      version = "~> 4.8"
    }
  }
}

provider "vercel" {
  api_token = var.vercel_api_token
  team      = var.vercel_team_id
}

resource "vercel_project" "lamu_tours" {
  name           = var.project_name
  root_directory = "."
  build_command  = "npm --prefix frontend ci && npm --prefix frontend run build"
}

output "vercel_project_id" {
  description = "Use this value for the VERCEL_PROJECT_ID GitHub Actions secret."
  value       = vercel_project.lamu_tours.id
}