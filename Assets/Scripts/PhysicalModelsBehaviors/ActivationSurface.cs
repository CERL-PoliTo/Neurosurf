using UnityEngine;

public class ActivationSurface : MonoBehaviour
{
    private static readonly int Colormap = Shader.PropertyToID("_Colormap");
    private Mesh mesh;
    private MeshRenderer meshRenderer;
    private LslReceiver receiver;
    private int nbVertices;

    private string streamName;
    private Material streamMaterial;
    private Material noStreamMaterial;

    private double[] values;
    private double minValue = double.MaxValue;
    private double maxValue = double.MinValue;
    private Color[] colors;

    [SerializeField] private ModelLayerSelector objectSelector;

    private void Start()
    {
        mesh = GetComponent<MeshFilter>().mesh;
        nbVertices = mesh.vertices.Length;
        colors = new Color[nbVertices];
        
        streamMaterial = GameManager.instance.GetStreamMaterial(objectSelector);
        noStreamMaterial = GameManager.instance.GetNoStreamMaterial(objectSelector);
        meshRenderer  = GetComponent<MeshRenderer>();
        meshRenderer.material = noStreamMaterial;
        noStreamMaterial = meshRenderer.material; // this is required to keep a reference to the instantiated material
        
        streamName = GameManager.instance.GetLslStreamName(objectSelector);
        receiver = new LslReceiver(nbVertices, streamName);
    }

    private void Update()
    {
        if (receiver == null || GameManager.instance == null) return;

        receiver.GetSamples();
        
        if (receiver.DatasetQueue.Count <= 0) return;
        if (meshRenderer.material == noStreamMaterial)
        {
            meshRenderer.material = streamMaterial;
            meshRenderer.material.renderQueue = GameManager.instance.GetRenderQueue(objectSelector);
            SetShaderProperty(GameManager.instance.GetTransparencyValue(objectSelector));
        }

        try
        {
            values = receiver.DatasetQueue.Dequeue();
        }
        catch (System.InvalidOperationException)
        {
            if (values == null)
                return;
        }

        if (GameManager.instance.perFrameNormalization)
        {
            minValue = float.MaxValue;
            maxValue = float.MinValue;
        }

        foreach (var t in values)
        {
            if (minValue > t) minValue = t;
            if (maxValue < t) maxValue = t;
        }

        // normalize values in the range [0,1]
        double range = maxValue - minValue;
        if (range == 0)
        {
            Color fillColor = new Color(0f,0f,0f,0f);
            for (int i = 0; i < nbVertices; i++)
            {
                colors[i] = fillColor;
            }
        }
        else
        {
            for (int i = 0; i < values.Length; i++)
            {
                double alphaValue = (values[i] - minValue) / range;
                colors[i] = new Color(0f, 0f, 0f, (float)alphaValue);
            }
        }
            
        mesh.colors = colors;
    }

    public void SetShaderProperty(float value)
    {
        meshRenderer.material.SetFloat(GameManager.instance.GetPropertyAlpha(objectSelector), value);
    }

    public void SetShaderColormap(Texture2D texture)
    {
        meshRenderer.material.SetTexture(Colormap, texture);
    }

    private void OnDestroy()
    {
        receiver?.Close();
        receiver = null;
    }

}
