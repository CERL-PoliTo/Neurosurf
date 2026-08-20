Shader "Unlit/Grid"
{
    Properties
    {
        _GridColor ("Grid Color", Color) = (1, 1, 1, 1)
        _BaseColor ("Base Color", Color) = (1, 1, 1, 0)
        _GridSpacing ("Grid Spacing", Float) = 1
        _LineThickness ("Line Thickness (px)", Float) = 0.1
        _ODistance ("Start Transparency Distance", Float) = 5
        _TDistance ("Full Transparency Distance", Float) = 10
    }
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" }
        LOD 100

        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 vertex   : SV_POSITION;
                float2 uv       : TEXCOORD0;
                float3 worldPos : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            fixed4 _GridColor;
            fixed4 _BaseColor;
            float _GridSpacing;
            float _LineThickness;
            float _ODistance;
            float _TDistance;

            v2f vert (appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);

                o.vertex = UnityObjectToClipPos(v.vertex);

                float3 worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.worldPos = worldPos;
                o.uv = worldPos.xz / _GridSpacing;

                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                // Grid lines via UV wrapping and derivative-based AA
                float2 wrapped = frac(i.uv) - 0.5f;
                float2 range = abs(wrapped);
                float2 speeds = fwidth(i.uv);
                float2 pixelRange = range / speeds;

                float lineWeight = saturate(min(pixelRange.x, pixelRange.y) - _LineThickness);
                fixed4 col = lerp(_GridColor, _BaseColor, lineWeight);

                // Distance-based alpha falloff
                float3 viewDirW = _WorldSpaceCameraPos - i.worldPos;
                float viewDist = length(viewDirW);

                float distanceRange = max(_TDistance - _ODistance, 0.0001);
                float falloff = saturate((viewDist - _ODistance) / distanceRange);

                col.a *= (1.0f - falloff);
                return col;
            }
            ENDCG
        }
    }
}
