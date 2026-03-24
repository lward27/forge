{{/*
Common labels
*/}}
{{- define "forge-platform.labels" -}}
app.kubernetes.io/name: {{ .Values.forgePlatform.name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "forge-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ .Values.forgePlatform.name }}
{{- end }}
