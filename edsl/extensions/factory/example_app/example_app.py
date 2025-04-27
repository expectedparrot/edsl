from edsl.extensions.factory.app_factory import create_app
from edsl.extensions.factory.config import Settings

# Create custom settings if needed
custom_settings = Settings(
    app_name="My Custom App",
    version="1.0.0",
    api_prefix="/api/v2",
    debug=False
)

# Create app with example variant router and custom settings
app = create_app("example_variant", custom_settings)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("example_app:app", host="0.0.0.0", port=8081, reload=True)