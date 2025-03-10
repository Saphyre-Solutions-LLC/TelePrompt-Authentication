# TelePrompt-Authentication
Handles Customer Data - Integrate With CRM - Authenticates User's Login

## GitHub Continuous Deployment for Your Authentication App

Yes, Enable Continuous Deployment ✅

For an authentication application that connects to your CRM, enabling continuous deployment from GitHub is highly beneficial for several reasons:

### Benefits for Your Authentication App:
- Fast Updates: Quickly deploy security patches and authentication flow improvements
- Version Control: Track all changes to your authentication system
- Testing Automation: Add automated tests to verify OAuth flows work before deployment
- Consistency: Eliminate manual deployment errors that could break authentication
- Audit Trail: Important for security tracking of who changed authentication code and when

### Configuration Recommendations:
- Repository Structure: Create a dedicated repo for your authentication handler
- Branch Protection: Enable branch protection rules for main/master to require code reviews
- Environment Variables: Store your Redis connection strings and CRM credentials as GitHub secrets
- Testing: Add authentication flow tests that run before deployment

### About Basic Authentication:
Recommendation: Disable Basic Authentication since:
- You're using GitHub Actions which has its own secure authentication method
- Basic auth creates an unnecessary security risk for your authentication system
- Modern CI/CD patterns avoid basic auth in favor of token-based or certificate authentication

Setting up continuous deployment now will save you time later as you enhance your authentication flows and CRM integrations, especially if you need to add features like:
- Enhanced token handling
- User profile enrichment before CRM storage
- New authentication providers
- Improved error handling

## Repository Setup for Authentication App

### 1. Repository Configuration
Make your repository PRIVATE ⚠️
- Authentication code should never be public
- Contains secrets (even if using environment variables)
- Exposes security practices of your organization

### 2. Repository Initial Setup
- Create a new private repository in GitHub
- Initialize with a README.md
- Create the following folder structure:
  ```
  /src
  /.github/workflows
  ```

### 3. Minimal Code Needed
Create a simple initial web app in your preferred language. For example, in C#/.NET:
```csharp
// Program.cs (minimal example)
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddAuthentication();
builder.Services.AddAuthorization();

// Add Redis cache
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("RedisConnection");
});

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/", () => "Authentication Service Running");
app.Run();
```

### 4. GitHub Actions Workflow File
Create `.github/workflows/azure-deploy.yml`:
```yaml
name: Deploy to Azure App Service

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup .NET
      uses: actions/setup-dotnet@v1
      with:
        dotnet-version: '6.0.x'
    
    - name: Build
      run: dotnet build --configuration Release
      
    - name: Publish
      run: dotnet publish -c Release -o ${{env.DOTNET_ROOT}}/myapp
      
    - name: Deploy to Azure
      uses: azure/webapps-deploy@v2
      with:
        app-name: 'your-app-name'
        publish-profile: ${{ secrets.AZURE_PUBLISH_PROFILE }}
        package: ${{env.DOTNET_ROOT}}/myapp
```

### 5. Next Steps
Set up GitHub secrets:
- Go to your repository → Settings → Secrets
- Add `AZURE_PUBLISH_PROFILE` (download from your Azure App Service)
- Create `appsettings.json` with placeholders (no real secrets):
  ```json
  {
    "ConnectionStrings": {
      "RedisConnection": "#{REDIS_CONNECTION}#",
      "DefaultDatabase": "#{DATABASE_CONNECTION}#"
    },
    "Authentication": {
      "CrmApiEndpoint": "#{CRM_ENDPOINT}#"
    }
  }
  ```

Deploy your first version and verify the CI/CD pipeline works

This setup creates a secure foundation for your authentication service that connects to Redis and your CRM.

## Folder Structure Clarification
Here's the recommended folder structure for your authentication app:
```
YourRepository/
├── .github/
│   └── workflows/
│       └── azure-deploy.yml
├── src/
│   ├── TelepromptAuth/              # Main project folder
│   │   ├── Controllers/
│   │   ├── Services/
│   │   ├── Models/
│   │   ├── Data/
│   │   ├── Configuration/
│   │   ├── Program.cs
│   │   ├── Startup.cs
│   │   └── appsettings.json
│   └── TelepromptAuth.Tests/        # Test project folder
├── .gitignore
└── README.md
```
Key Points:
- `/src` is the parent folder containing all your source code
- All code-related folders go inside `/src`
- Only infrastructure files stay at root level:
  - `.github` folder
  - `.gitignore`
  - `README.md`
  - Solution file (.sln)

### Recommended .gitignore:
Create this at the root level:
```
## .NET Core
bin/
obj/
*.user
*.userosscache
*.suo
*.userprefs

## VS Code
.vscode/
.vs/

## Environment Files
*.env
appsettings.Development.json
appsettings.Production.json

## Redis
*.rdb

## Logs
logs/
*.log
```

This structure keeps your authentication code organized and follows industry best practices for enterprise applications. The separation of concerns makes it easier to:
- Manage dependencies
- Run tests
- Deploy code
- Maintain security
- Scale the application
