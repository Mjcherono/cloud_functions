# Cloud Function - Serverside Google Tag Manager Image Updater
This is a Cloud Function designed to check and update the GTM image currently deployed to the specified Cloud Run service.
## Getting Started

1. Clone this repository
2. Deploy with `gcloud builds deploy` to your GCP project
3. Trigger the Cloud Function (e.g. Cloud Scheduler once a day)

The function takes three parameters from the post body to work as expected
```
{
    "project_id": YOUR_PROJECT_ID,
    "region": REGION_OF_THE_CR_SERVICE,
    "service_name: SERVICE_NAME
}
```


# Loan Data Endpoints #

This repo has all endpoints required for loan customer details from the BigQuery. They include:

* Customer Details
* Customer Deliveries
* Customer Repayments
* Customer Payments

### Endpoints? ###

- **GET /payments**: Fetch payments data based on depot & date range
- **GET /deliveries**: Fetch deliveries data based on depot, date range & customer ID (optional)
- **GET /customers** ""
- **GET /repayments** ""


### How do I get set up? ###

* 1. Clone the repository

2. Install dependencies:
pip install -r requirements.txt


3. Set up environment variables:

    - `PROJECT_ID`: Your Google Cloud project ID.
    - `AUTH_TOKEN`: Authentication token for accessing the endpoints.

4. Deploy the Cloud Function to Google Cloud Platform.

    gcloud run deploy your-service-name \
    --image gcr.io/your-project/your-image \
    --platform managed \
    --set-env-vars PROJECT_ID=your-project-id,AUTH_TOKEN=your-auth-token \
    --region your-region


## Usage

To use the endpoints, make HTTP GET requests to the respective endpoints with required query parameters.

Example:
GET /payments?depot=ABSA&date_from=2022-01-01&date_to=2022-01-31&page=1