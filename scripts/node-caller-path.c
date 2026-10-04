/* Public Node environment setup before exec. Native interpreter for Darwin. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
  (void)argc;
  char *cwd = getcwd(NULL, 0), *parent, *paths;
  const char *inherited = getenv("NODE_PATH");
  if (!cwd || !(parent = strdup(cwd))) { perror("getcwd/strdup"); return 126; }
  char *slash = strrchr(parent, '/');
  if (slash) slash[slash == parent ? 1 : 0] = '\0';
  if (asprintf(&paths, "%s/node_modules:%s%s%s", cwd, parent,
               inherited && *inherited ? ":" : "", inherited ? inherited : "") < 0
      || setenv("NODE_PATH", paths, 1)) { perror("NODE_PATH"); return 126; }
  free(cwd); free(parent); free(paths);
  argv[0] = NODE_BIN;
  execv(NODE_BIN, argv);
  perror("execv node");
  return 126;
}
