#!/bin/zsh
# Lo llama la Acción rápida «Unir panel» de Finder con las capturas (o la carpeta) elegidas.
# Avisa con notificaciones, deja el detalle en ultimo-panel.log y abre el resultado en Vista Previa.
DIR="${0:A:h}"
LOG="$DIR/ultimo-panel.log"
[ $# -eq 0 ] && exit 0

osascript -e 'display notification "Uniendo capturas…" with title "Unir panel"'
"$DIR/.venv/bin/python" "$DIR/unir_panel.py" "$@" > "$LOG" 2>&1
estado=$?

if [ $estado -ne 0 ]; then
    motivo=$(grep '^Error' "$LOG" | head -1 | sed 's/"/\\"/g')
    osascript -e "display notification \"${motivo:-Algo falló. Abre el detalle.}\" with title \"Unir panel\""
    open -e "$LOG"
    exit 1
fi

salida=$(sed -n 's/^Salida: //p' "$LOG")
resumen=$(grep '^Listo' "$LOG" | sed 's/"/\\"/g')
osascript -e "display notification \"$resumen\" with title \"Unir panel\""
open -a Preview "$salida"
