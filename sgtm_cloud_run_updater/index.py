# Will take the active revision of the specified Cloud Run service and check if the GTM image sha 
#  is the same as the latest stable version of the GTM image. 
#  In case of mismatch a new revision will be created copying the variables and resources from the last active revision.
 
#  @param req Post request keys required: project_id, region, service_name
#  @returns The status of the currently deployed Cloud Run service

from google.cloud import run_v2
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Initialize Cloud Run clients
run_client = run_v2.RevisionsClient()
service_client = run_v2.ServicesClient()

@app.route('/check_cloud_run', methods=['POST'])
def check_cloud_run():
    # Validate request body
    data = request.get_json()
    if not all(k in data for k in ("project_id", "region", "service_name")):
        return jsonify({"success": "false", "message": "Wrong / Missing request body"}), 500

    params = {
        "project_id": data["project_id"],
        "region": data["region"],
        "service_name": data["service_name"]
    }

    try:
        return check_cloud_run_internal(params)
    except Exception as e:
        return jsonify({"success": "false", "message": str(e)}), 500

def check_cloud_run_internal(params):
    parent = f"projects/{params['project_id']}/locations/{params['region']}/services/{params['service_name']}"
    request = {"parent": parent}

    revisions_list = []
    active_revision = None

    # List revisions for the service
    iterable = run_client.list_revisions(request=request)
    for revision in iterable:
        revisions_list.append(revision)

    # Find the active revision
    for revision in revisions_list:
        for condition in revision.conditions:
            if condition.type == "Active" and condition.state == "CONDITION_SUCCEEDED":
                active_revision = revision
                break

    if not active_revision:
        raise Exception("No active revision found")

    current_image_key = active_revision.containers[0].image.split(":")[1]
    print(f"Currently deployed GTM image version sha: {current_image_key}")

    # Fetch the latest stable GTM image
    url = 'https://gcr.io/v2/cloud-tagging-10302018/gtm-cloud-image/tags/list'
    response = requests.get(url)
    response.raise_for_status()

    image_manifest = response.json().get('manifest', {})
    stable_image_key, stable_image_tags = None, None

    # Search for the stable image in the manifest
    for release, data in image_manifest.items():
        tags = data.get("tag", [])
        if isinstance(tags, list) and 'stable' in tags:
            stable_image_key = release.split(":")[1]
            stable_image_tags = tags
            break

    print(f"Stable GTM image sha: {stable_image_key} and tags {stable_image_tags}")

    # Check if the deployed image is different from the stable one
    if stable_image_key != current_image_key:
        print(f"Versions are different: Deploying a new revision to catch latest stable image: {stable_image_key}")
        print(active_revision)

        service = {
            "name": f"projects/{params['project_id']}/locations/{params['region']}/services/{params['service_name']}",
            "template": {
                "containers": [{
                    "image": "gcr.io/cloud-tagging-10302018/gtm-cloud-image:stable",
                    "env": active_revision.containers[0].env,
                    "resources": active_revision.containers[0].resources,
                    "liveness_probe": active_revision.containers[0].liveness_probe,
                    "startup_probe": active_revision.containers[0].startup_probe,
                }],
                "scaling": {
                    "min_instance_count": active_revision.scaling.min_instance_count,
                    "max_instance_count": active_revision.scaling.max_instance_count
                }
            }
        }

        revision_request = {"service": service}
        operation = service_client.update_service(request=revision_request)
        revision_response = operation.result()

        return jsonify({
            "status": "updated successfully",
            "gtm-version": current_image_key,
            "latest-image-version": stable_image_key
        }), 200

    return jsonify({
        "status": "no update needed",
        "gtm-version": current_image_key,
        "latest-image-version": stable_image_key
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
