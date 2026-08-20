using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.Serialization;

[RequireComponent(typeof(Slider))]
public class TransparencySlider : MonoBehaviour
{
    [FormerlySerializedAs("brainObject")] [SerializeField] private ModelLayerSelector modelLayer;
    [SerializeField] private TMP_Text label;

    private Slider slider;

    private void Awake()
    {
        slider = GetComponent<Slider>();
    }

    private void OnEnable()
    {
        float value = GameManager.instance.GetTransparencyValue(modelLayer);
        slider.SetValueWithoutNotify(value);
        UpdateLabel(value);
        
        slider.onValueChanged.AddListener(OnSliderValueChanged);
    }

    private void OnDisable()
    {
        slider.onValueChanged.RemoveListener(OnSliderValueChanged);
    }

    private void OnSliderValueChanged(float value)
    {
        GameManager.instance.SetTransparencyValue(modelLayer, value);
        UpdateLabel(value);
    }

    private void UpdateLabel(float value)
    {
        if (label != null)
        {
            label.text = value.ToString("F2");
        }
    }
}
