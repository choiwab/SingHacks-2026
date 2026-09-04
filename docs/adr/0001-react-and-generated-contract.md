# Use React and a generated projection contract

The Monday Brief interface will use React with Vite instead of hand-written DOM updates. Pydantic and FastAPI remain the source of truth for the versioned Monday Brief projection, and the TypeScript contract is generated from OpenAPI and committed so Python and React cannot silently drift. This adds a contract-generation check to development and CI, but gives routed screens one typed projection interface and keeps projection rules out of the browser.
