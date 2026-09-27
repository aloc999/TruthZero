# TRUTHZERO Swarm Scan — GitHub Action

Run the swarm in CI and upload SARIF to code scanning.

## Publish to Marketplace (maintainers)
1. Tag a stable release: `git tag v0.11.0 && git push origin v0.11.0`
2. Move the major-version tag: `git tag -f v0 && git push -f origin v0`
   (Actions users pin `aloc999/TRUTHZERO/deploy/github-action@v0`)
3. Add the action icon/topics on the repo page. Marketplace listing for
   actions is automatic once `action.yml` exists on the default branch.

## Use
```yaml
- uses: aloc999/TRUTHZERO/deploy/github-action@v0
  with:
    target: https://staging.example.com   # authorized only
    playbook: ci-cd
```
