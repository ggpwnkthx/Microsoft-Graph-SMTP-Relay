# Microsoft Graph SMTP Relay
SMTP relay for sending emails via the Microsoft Graph API

## Note
This is not a proxy. Email data is parsed and converted into JSON so it can be sent using the Microsoft Graph API. Not all email RFC standards are supported, but efforts have been made in this project to generalize them.

## Introduction
Microsoft has, for years, been trying to push everyone away from using SMTP with baisc authentication (username + password), which I completely support. However, not a lot of the open source projects I use have caught on to adding OAuth2 based authentication for sending out email. Heck, even many enterprise level products still require using basic authentication. There are some official work arounds, but all of them involve identity authentication methods that either don't work in many cases (where an IP addess may change frequently) or require disabling certain security policies that can be dangerous.

This service is ideal for developers and organizations looking to integrate email functionalities within their applications hosted on cloud platforms, microservices architectures, or any situation where traditional SMTP access poses challenges. With easy setup, comprehensive documentation, and Docker support, it streamlines the process of sending emails through Microsoft's secure and reliable Graph API, thereby enhancing application communication strategies with minimal overhead.

## Getting Started

### Prerequisites
- Docker
- Python 3.8 or higher
- A Microsoft Azure account with access to Microsoft Graph API

### Local Testing
1. Clone this repository to your local machine.
2. Navigate to the cloned directory.
3. Copy `.env.sample` to `.env` and fill in the necessary environment variables.
4. Build the Docker container: `docker build -t microsoft-graph-smtp-relay`.
5. Run the container: `docker run -d --name smtp-relay microsoft-graph-smtp-relay`

## Configuration
The `.env.sample` file contains all necessary used configuration keys with partial examples.

### Azure Active Directory / Entra Registered App
1. Create a new Registed Application.
    - The **Application (client) ID** should be the **CLIENT_ID** environmental variable.
    - The **Directory (tenant) ID** should be appended to `https://login.microsoftonline.com/` to be the **AUTHORITY** environmental variable.
2. Go to the **Certificates & secrets** page and create a new secret.
    - The **Value** for that secret should be the **CLIENT_SECRET** environmental variable.
3. Go to the **API permissions** page.
    - Remove all existing permissions if this registered app will only be used for the SMTP relay.
    - Click **Add a permission**.
    - Click **Microsoft Graph**.
    - Click **Application permissions**.
    - Search for **mail**.
    - Select the following checkboxes from "Mail" register:
        - **Mail.Send** - required for mail submission
        - **Mail.ReadWrite** - required for mail draft with upload sessions
    - Click **Add permission**

## Usage

This service can be deployed in container orchestration environments using Docker Compose or Kubernetes. Examples provided in the `examples` directory demonstrate the configuration needed for each method.

### Using Docker Compose

The `docker-compose.yaml` file in the `examples` directory provides a template for deploying the SMTP Relay Service as a container. To use it:

1. Ensure Docker Compose is installed on your system.
2. Navigate to the `examples` directory.
3. Review and adjust the `docker-compose.yaml` file as necessary, ensuring environment variables are set according to your specific requirements.
4. Run the following command to start the service: `docker-compose up`

This will pull the necessary image and start the SMTP Relay Service as defined in the Docker Compose configuration.

### Using Kubernetes

For deployment in a Kubernetes cluster, the `k8s.yaml` file offers a detailed manifest for setting up the service. To deploy:

1. Ensure you have kubectl installed and configured to interact with your Kubernetes cluster.
2. Navigate to the `examples` directory.
3. Review the `k8s.yaml` file, adjusting the deployment specifications and environment variables to fit your environment.
4. Apply the configuration to your cluster with: `kubectl apply -f k8s.yaml`

This will create the necessary Kubernetes resources (e.g., Deployment, Service) to run the SMTP Relay Service within your cluster.

Both methods provide a scalable and manageable way to incorporate email functionality into your applications, leveraging the power of Microsoft Graph API through the SMTP Relay Service.

## Development
The `.devcontainer` directory contains VS Code and Docker configuration files for setting up a development environment inside a container.
The `app` directory contains the source code of the service.
Use the provided `dockerfile` for development and testing.

**Implementation of middleware is supported and documented in [MIDDLEWARE.md](./MIDDLEWARE.md)**

## Testing
The `test` directory includes a basic client script that can be used to test the relay service.

## Contributing
We welcome contributions to this project! Please refer to the `LICENSE` for more details on contributing and the terms of use.

## License
This project is licensed under the terms of the MIT License. See the `LICENSE` file for more details.

## Support
For support and feature requests, please open an issue in the repository's issue tracker.
